import csv
import json
import os
import random
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
from gtts import gTTS
from io import BytesIO
import pygame
import matplotlib.pyplot as plt
from deep_translator import GoogleTranslator

# --- Dosya Yolları ---
WORDS_FILE = "words.csv"
STATS_FILE = "stats.json"
MISTAKES_FILE = "mistakes.txt"

# --- Global Değişkenler ---
word_list = []
stats = {}
mode = None
session_words = []
current_index = 0
start_time = 0
score = 0

pygame.mixer.init()

# --- Fonksiyonlar ---

def pronounce(text):
    """Kelimeyi seslendirir"""
    try:
        tts = gTTS(text=text, lang="en")
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        pygame.mixer.music.load(fp, "mp3")
        pygame.mixer.music.play()
    except Exception as e:
        print("Seslendirme hatası:", e)

def load_words():
    """Kelime listesini CSV'den yükler"""
    global word_list
    if not os.path.exists(WORDS_FILE):
        raise RuntimeError(f"{WORDS_FILE} bulunamadı!")
    with open(WORDS_FILE, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        word_list = [row for row in reader if len(row) >= 3]
    if not word_list:
        raise RuntimeError(f"{WORDS_FILE} dosyası boş veya format hatası!")

def load_stats():
    """SM-2 istatistiklerini yükler"""
    global stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as sf:
                stats = json.load(sf)
        except Exception:
            stats = {}
    else:
        stats = {}

def save_stats():
    """İstatistikleri kaydeder"""
    with open(STATS_FILE, "w", encoding="utf-8") as sf:
        json.dump(stats, sf, indent=2, ensure_ascii=False)

def add_to_mistakes(question, your_answer, correct_answer):
    """Hatalı cevapları mistakes.txt dosyasına kaydeder"""
    with open(MISTAKES_FILE, "a", encoding="utf-8") as mf:
        mf.write(f"Soru: {question}\n- Senin cevabın: {your_answer}\n- Doğru cevap: {correct_answer}\n\n")

def load_mistakes_words():
    """Mistakes dosyasından hatalı kelimeleri yükler"""
    if not os.path.exists(MISTAKES_FILE):
        return []
    with open(MISTAKES_FILE, encoding="utf-8") as mf:
        lines = mf.readlines()
    words = []
    for line in lines:
        if line.startswith("Soru: "):
            words.append(line[6:].strip())
    return words

def clear_mistakes_for_word(word):
    """Bir kelime için mistakes dosyasındaki kayıtları temizler"""
    if not os.path.exists(MISTAKES_FILE):
        return
    import re
    with open(MISTAKES_FILE, encoding="utf-8") as mf:
        content = mf.read()
    pattern = re.compile(rf"(Soru: {re.escape(word)}\n(?:-.*\n)*\n)", re.MULTILINE)
    content_new = pattern.sub("", content)
    with open(MISTAKES_FILE, "w", encoding="utf-8") as mf:
        mf.write(content_new)

def sm2_update(word, quality):
    """SM-2 algoritmasına göre istatistikleri günceller"""
    key = word[0]
    if key not in stats:
        stats[key] = {"interval": 0, "repetitions": 0, "ef": 2.5, "due": 0, "correct_streak": 0,
                      "daily_correct": 0, "daily_wrong": 0, "last_study": 0}
    data = stats[key]
    now = time.time()
    data["last_study"] = now
    if quality >= 3:
        data["correct_streak"] += 1
        data["daily_correct"] = data.get("daily_correct", 0) + 1
        if data["repetitions"] == 0:
            data["interval"] = 1
        elif data["repetitions"] == 1:
            data["interval"] = 6
        else:
            data["interval"] = round(data["interval"] * data["ef"])
        data["repetitions"] += 1
        data["ef"] = max(1.3, data["ef"] + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        data["due"] = now + data["interval"] * 24 * 3600
        if data["correct_streak"] >= 10 and mode != "hardcore":
            if word in session_words:
                session_words.remove(word)
    else:
        data["correct_streak"] = 0
        data["daily_wrong"] = data.get("daily_wrong", 0) + 1
        data["repetitions"] = 0
        data["interval"] = 1
        data["due"] = now + 24 * 3600

def create_session():
    """Seans için kelime listesini oluşturur"""
    global session_words
    now = time.time()
    if mode == "rutin":
        session_words = []
        for w in word_list:
            key = w[0]
            if key not in stats:
                stats[key] = {"interval": 0, "repetitions": 0, "ef": 2.5, "due": 0, "correct_streak": 0}
            if stats[key]["due"] <= now:
                session_words.append(w)
        if not session_words:
            messagebox.showinfo("Bilgi", "Bugün tekrar edilmesi gereken kelime yok!")
            root.quit()
            return
        if len(session_words) > 50:
            session_words = random.sample(session_words, 50)
    elif mode == "hatalar":
        mistake_words = load_mistakes_words()
        session_words = [w for w in word_list if w[0] in mistake_words]
        if not session_words:
            messagebox.showinfo("Bilgi", "Hata oranı yüksek kelime yok!")
            root.quit()
            return
    elif mode == "hardcore":
        session_words = word_list.copy()
        if not session_words:
            messagebox.showinfo("Bilgi", "Kelime listesi boş!")
            root.quit()
            return
    random.shuffle(session_words)

def show_question():
    """Şu anki kelimeyi ve örnek cümleyi gösterir"""
    global current_index, start_time
    if current_index >= len(session_words):
        messagebox.showinfo("Tebrikler!", f"Seans bitti! Skorunuz: {score}")
        save_stats()
        root.quit()
        return
    eng, tur, example = session_words[current_index]

    # Soru türü: %50 İngilizce, %50 Türkçe
    if random.choice([True, False]):
        question_label.config(text=eng)
        example_label.config(text=example)
        root.current_answer = tur.lower()
        root.question_word = eng
        root.is_eng_question = True
        pronounce(eng)
    else:
        question_label.config(text=tur)
        example_label.config(text="")
        root.current_answer = eng.lower()
        root.question_word = tur
        root.is_eng_question = False
        pronounce(eng)

    answer_entry.delete(0, tk.END)
    feedback_label.config(text="")
    start_time = time.time()

def check_answer(event=None):
    """Kullanıcı cevabını kontrol eder, skor ve SM-2 günceller"""
    global current_index, score
    user_answer = answer_entry.get().strip().lower()
    correct_answer = root.current_answer
    time_taken = time.time() - start_time

    # Kaliteyi cevap süresine göre belirle
    if time_taken < 3:
        quality = 5
    elif time_taken < 7:
        quality = 4
    elif time_taken < 12:
        quality = 3
    else:
        quality = 2

    question_word = root.question_word

    if user_answer == correct_answer:
        feedback_label.config(text="Doğru!", fg="green")
        score += 1
        sm2_update(session_words[current_index], quality)
        clear_mistakes_for_word(question_word)
        score_label.config(text=f"Skor: {score}")
        current_index += 1
        root.after(1000, show_question)
    else:
        feedback_label.config(text=f"Yanlış! Doğru cevap: {correct_answer}", fg="red")
        add_to_mistakes(question_word, user_answer, correct_answer)
        sm2_update(session_words[current_index], 1)
        current_index += 1
        root.after(1500, show_question)

def show_stats():
    daily_correct = sum(s.get("daily_correct", 0) for s in stats.values())
    daily_wrong = sum(s.get("daily_wrong", 0) for s in stats.values())
    total_words = len(stats)

    if daily_correct + daily_wrong == 0:
        messagebox.showinfo("İstatistikler", "Bugün henüz hiç kelime çalışılmamış.")
        return

    labels = ['Doğru', 'Yanlış']
    values = [daily_correct, daily_wrong]
    colors = ['green', 'red']

    plt.figure(figsize=(5, 5))
    plt.title('Bugünkü Doğru / Yanlış Sayısı')
    plt.pie(values, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140)
    plt.axis('equal')
    plt.show()

    messagebox.showinfo("İstatistikler",
                        f"Toplam Kelime: {total_words}\n"
                        f"Bugün Doğru Cevap: {daily_correct}\n"
                        f"Bugün Yanlış Cevap: {daily_wrong}\n")

def choose_meaning(meanings):
    """Çok anlamlı kelimelerde seçim yaptırır"""
    choice_window = tk.Toplevel(root)
    choice_window.title("Anlam Seçimi")
    tk.Label(choice_window, text="Lütfen anlamı seçin:", font=("Arial", 12)).pack(pady=10)

    chosen = tk.StringVar()

    for m in meanings:
        rb = tk.Radiobutton(choice_window, text=m, variable=chosen, value=m, font=("Arial", 11))
        rb.pack(anchor="w")

    def confirm():
        if chosen.get():
            choice_window.destroy()
        else:
            messagebox.showwarning("Uyarı", "Lütfen bir anlam seçin!")

    tk.Button(choice_window, text="Seç", command=confirm).pack(pady=10)

    choice_window.transient(root)
    choice_window.grab_set()
    root.wait_window(choice_window)

    return chosen.get()

def add_word_ui():
    """Kelime ekleme ekranı"""
    def translate_and_add():
        turkce = turkce_entry.get().strip()
        if not turkce:
            messagebox.showwarning("Uyarı", "Lütfen Türkçe kelime girin!")
            return

        try:
            # İngilizce anlamları al
            meanings = GoogleTranslator(source='tr', target='en').translate(turkce)
            # Çoklu anlam varsa listeye ayır
            if "," in meanings or ";" in meanings:
                meaning_list = [m.strip() for m in meanings.replace(";", ",").split(",")]
            else:
                meaning_list = [meanings]

            if len(meaning_list) > 1:
                chosen_meaning = choose_meaning(meaning_list)
            else:
                chosen_meaning = meaning_list[0]

            example = f"This is a {chosen_meaning}."

            # Aynı kelimeyi kontrol et
            for w in word_list:
                if w[0].lower() == chosen_meaning.lower():
                    messagebox.showinfo("Bilgi", f"'{chosen_meaning}' kelimesi zaten listede var!")
                    return

            with open(WORDS_FILE, "a", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerow([chosen_meaning, turkce, example])

            word_list.append([chosen_meaning, turkce, example])
            messagebox.showinfo("Başarılı", f"{turkce} kelimesi başarıyla eklendi!")
            turkce_entry.delete(0, tk.END)

        except Exception as e:
            messagebox.showerror("Hata", f"Çeviri sırasında hata: {e}")

    add_win = tk.Toplevel(root)
    add_win.title("Kelime Ekle")

    tk.Label(add_win, text="Türkçe kelime girin:", font=("Arial", 12)).pack(pady=10)
    turkce_entry = tk.Entry(add_win, font=("Arial", 14))
    turkce_entry.pack(pady=5)
    turkce_entry.focus_set()

    tk.Button(add_win, text="Ekle", command=translate_and_add).pack(pady=10)
    tk.Button(add_win, text="Kapat", command=add_win.destroy).pack(pady=5)

    add_win.transient(root)
    add_win.grab_set()
    root.wait_window(add_win)

# --- Ana Tkinter Penceresi ---
root = tk.Tk()
root.title("İngilizce Kelime Öğrenme")

# Ana menü buton fonksiyonları
def start_routine():
    global mode, current_index, score
    mode = "rutin"
    current_index = 0
    score = 0
    create_session()
    show_question()

def start_errors():
    global mode, current_index, score
    mode = "hatalar"
    current_index = 0
    score = 0
    create_session()
    show_question()

def start_hardcore():
    global mode, current_index, score
    mode = "hardcore"
    current_index = 0
    score = 0
    create_session()
    show_question()

# Ana menü arayüzü
menu_frame = tk.Frame(root)
menu_frame.pack(padx=30, pady=30)

tk.Label(menu_frame, text="Mod Seçimi", font=("Arial", 18)).pack(pady=10)
tk.Button(menu_frame, text="Günlük Rutin Modu", width=20, command=start_routine).pack(pady=5)
tk.Button(menu_frame, text="Hatalar Modu", width=20, command=start_errors).pack(pady=5)
tk.Button(menu_frame, text="Hardcore Modu", width=20, command=start_hardcore).pack(pady=5)
tk.Button(menu_frame, text="Kelime Ekle", width=20, command=add_word_ui).pack(pady=15)
tk.Button(menu_frame, text="İstatistikleri Göster", width=20, command=show_stats).pack(pady=5)

# Soru ve cevap için çerçeve (mod seçildikten sonra gösterilecek)
qa_frame = tk.Frame(root)

question_label = tk.Label(qa_frame, text="", font=("Arial", 20))
question_label.pack(pady=10)

example_label = tk.Label(qa_frame, text="", font=("Arial", 14), fg="gray")
example_label.pack()

answer_entry = tk.Entry(qa_frame, font=("Arial", 16))
answer_entry.pack(pady=15)

feedback_label = tk.Label(qa_frame, text="", font=("Arial", 16))
feedback_label.pack()

score_label = tk.Label(qa_frame, text="Skor: 0", font=("Arial", 16))
score_label.pack(pady=5)

def enter_key(event):
    check_answer()

answer_entry.bind("<Return>", enter_key)

# Mod seçilip quiz başlayınca menüyü gizle, soru-cevap çerçevesini göster
def show_question_wrapper():
    menu_frame.pack_forget()
    qa_frame.pack(padx=20, pady=20)
    answer_entry.focus_set()

# Başla butonlarında çağrılacak güncelleme
def start_routine():
    global mode, current_index, score
    mode = "rutin"
    current_index = 0
    score = 0
    create_session()
    show_question_wrapper()
    show_question()

def start_errors():
    global mode, current_index, score
    mode = "hatalar"
    current_index = 0
    score = 0
    create_session()
    show_question_wrapper()
    show_question()

def start_hardcore():
    global mode, current_index, score
    mode = "hardcore"
    current_index = 0
    score = 0
    create_session()
    show_question_wrapper()
    show_question()

# --- Program Başlangıcı ---
try:
    load_words()
    load_stats()
except Exception as e:
    messagebox.showerror("Hata", str(e))
    root.destroy()

root.mainloop()
