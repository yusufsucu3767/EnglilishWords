import csv
import json
import os
import random
import time
import tkinter as tk
from tkinter import messagebox
from gtts import gTTS
from io import BytesIO
import pygame

# --- DOSYA YOLLARI ---
WORDS_FILE = "words.csv"
STATS_FILE = "stats.json"
MISTAKES_FILE = "mistakes.txt"

# --- GLOBALLER ---
word_list = []       # tüm kelimeler (eng, tur, example)
stats = {}           # sm-2, tekrar, quality bilgisi
mode = None          # seçilen mod: "rutin", "hatta", "hardcore"
session_words = []   # seçilen moddaki session listesi
current_index = 0    # o anki sorulan kelime indeksi
start_time = 0       # cevap süresi için

pygame.mixer.init()

# --- SESLENDİRME ---
def pronounce(text):
    try:
        tts = gTTS(text=text, lang="en")
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        pygame.mixer.music.load(fp, "mp3")
        pygame.mixer.music.play()
    except Exception as e:
        print("Seslendirme hatası:", e)

# --- VERİ YÜKLEME ---
def load_words():
    global word_list
    if not os.path.exists(WORDS_FILE):
        raise RuntimeError(f"{WORDS_FILE} bulunamadı!")

    with open(WORDS_FILE, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        word_list = [row for row in reader if len(row) >= 3]

    if not word_list:
        raise RuntimeError(f"{WORDS_FILE} dosyası boş veya format hatası!")

def load_stats():
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
    with open(STATS_FILE, "w", encoding="utf-8") as sf:
        json.dump(stats, sf, indent=2, ensure_ascii=False)

# --- MISTAKES.DOSYASI İŞLEMLERİ ---
def add_to_mistakes(question, your_answer, correct_answer):
    with open(MISTAKES_FILE, "a", encoding="utf-8") as mf:
        mf.write(f"Soru: {question}\n")
        mf.write(f"- Senin cevabın: {your_answer}\n")
        mf.write(f"- Doğru cevap: {correct_answer}\n\n")

def load_mistakes_words():
    """mistakes.txt içinden kelimeleri alır (soru sütunu)"""
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
    """Bir kelime mistakes.txt den silinir (hatalar temizlenir)"""
    if not os.path.exists(MISTAKES_FILE):
        return
    with open(MISTAKES_FILE, encoding="utf-8") as mf:
        content = mf.read()
    # Soru: kelime ... bloklarını sil
    import re
    pattern = re.compile(rf"(Soru: {re.escape(word)}\n(?:-.*\n)*\n)", re.MULTILINE)
    content_new = pattern.sub("", content)
    with open(MISTAKES_FILE, "w", encoding="utf-8") as mf:
        mf.write(content_new)

# --- SEÇİLEN MODA GÖRE SESSION OLUŞTURMA ---
def create_session():
    global session_words
    if mode == "rutin":
        # Günlük rutin mod: tüm kelimeler içinden SM-2 ye göre tekrar zamanı gelenler
        session_words = []
        now = time.time()
        for i, w in enumerate(word_list):
            key = w[0]  # İngilizce kelime
            if key not in stats:
                # Yeni kelime ekle (başlangıç değerleri)
                stats[key] = {"interval": 0, "repetitions": 0, "ef": 2.5, "due": 0, "correct_streak": 0}
            if stats[key]["due"] <= now:
                session_words.append(w)
        if not session_words:
            messagebox.showinfo("Bilgi", "Bugün tekrar edilmesi gereken kelime yok!")
            exit()
        # Maks 50 kelime sınırı
        if len(session_words) > 50:
            session_words = random.sample(session_words, 50)

    elif mode == "hatalar":
        # Hata oranı %20 ve üzeri olan kelimeler: Mistakes.txt baz alınabilir.
        mistake_words = load_mistakes_words()
        session_words = [w for w in word_list if w[0] in mistake_words]
        if not session_words:
            messagebox.showinfo("Bilgi", "Hata oranı yüksek kelime yok!")
            exit()

    elif mode == "hardcore":
        # Tüm kelimeler + silinenler dahil rastgele
        session_words = word_list.copy()
        if not session_words:
            messagebox.showinfo("Bilgi", "Kelime listesi boş!")
            exit()

    random.shuffle(session_words)

# --- Spaced Repetition SM-2 ALGORİTMASI ---
def sm2_update(word, quality):
    """quality: 0-5 arası, 5 en iyi"""
    key = word[0]
    if key not in stats:
        stats[key] = {"interval": 0, "repetitions": 0, "ef": 2.5, "due": 0, "correct_streak": 0}

    data = stats[key]
    if quality >= 3:
        if data["repetitions"] == 0:
            data["interval"] = 1
        elif data["repetitions"] == 1:
            data["interval"] = 6
        else:
            data["interval"] = round(data["interval"] * data["ef"])
        data["repetitions"] += 1
        data["ef"] = max(1.3, data["ef"] + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        data["due"] = time.time() + data["interval"] * 24 * 3600
        # Eğer 10 kere arka arkaya doğruysa kelimeyi listeden kaldırabiliriz (hardcore dışında)
        if data["correct_streak"] >= 10 and mode != "hardcore":
            if word in session_words:
                session_words.remove(word)
    else:
        data["repetitions"] = 0
        data["interval"] = 1
        data["due"] = time.time() + 24 * 3600
        data["correct_streak"] = 0

# --- TKINTER ARAYÜZÜ ---
root = tk.Tk()
root.title("İngilizce Kelime Öğrenme")

# Mod seçimi için pencere
def select_mode():
    global mode
    m = mode_var.get()
    if m not in ("rutin", "hatalar", "hardcore"):
        messagebox.showerror("Hata", "Lütfen bir mod seçin!")
        return
    mode = m
    mode_window.destroy()
    create_session()
    show_question()

mode_window = tk.Toplevel(root)
mode_window.title("Mod Seçimi")
mode_var = tk.StringVar()

tk.Label(mode_window, text="Lütfen çalışma modunu seçin:", font=("Arial", 14)).pack(pady=10)
tk.Radiobutton(mode_window, text="Günlük Rutin Modu", variable=mode_var, value="rutin").pack(anchor="w", padx=20)
tk.Radiobutton(mode_window, text="Hatalar Modu (Yanlışları Çalış)", variable=mode_var, value="hatalar").pack(anchor="w", padx=20)
tk.Radiobutton(mode_window, text="Hardcore Mod (Tüm Kelimeler)", variable=mode_var, value="hardcore").pack(anchor="w", padx=20)
tk.Button(mode_window, text="Başla", command=select_mode).pack(pady=15)

# Ana pencere bileşenleri
question_label = tk.Label(root, text="", font=("Arial", 20))
question_label.pack(pady=15)

example_label = tk.Label(root, text="", font=("Arial", 14), fg="gray")
example_label.pack(pady=5)

answer_entry = tk.Entry(root, font=("Arial", 16))
answer_entry.pack(pady=15)
answer_entry.focus_set()

feedback_label = tk.Label(root, text="", font=("Arial", 16))
feedback_label.pack(pady=10)

score_label = tk.Label(root, text="Skor: 0", font=("Arial", 16))
score_label.pack(pady=5)

# Oyun değişkenleri
score = 0
current_index = 0
start_time = 0

def show_question():
    global current_index, start_time
    if current_index >= len(session_words):
        messagebox.showinfo("Tebrikler!", f"Seans bitti! Toplam skor: {score}")
        save_stats()
        root.quit()
        return
    eng, tur, example = session_words[current_index]

    # İngilizce soru ise örnek göster, Türkçe soru ise boş bırak
    if random.choice([True, False]):
        # İngilizce soru, cevap Türkçe
        question_label.config(text=eng)
        example_label.config(text=example)
        root.current_answer = tur.lower()
        root.question_word = eng
        root.is_eng_question = True
        pronounce(eng)
    else:
        # Türkçe soru, cevap İngilizce
        question_label.config(text=tur)
        example_label.config(text="")
        root.current_answer = eng.lower()
        root.question_word = tur
        root.is_eng_question = False
        pronounce(eng)  # Yine ingilizce kelimeyi seslendiriyoruz

    answer_entry.delete(0, tk.END)
    feedback_label.config(text="")
    start_time = time.time()

def check_answer(event=None):
    global current_index, score
    user_answer = answer_entry.get().strip().lower()
    correct_answer = root.current_answer

    time_taken = time.time() - start_time
    # Quality puanını 5 üzerinden cevap süresine göre hesaplayalım (örnek):
    if time_taken < 3:
        quality = 5
    elif time_taken < 7:
        quality = 4
    elif time_taken < 12:
        quality = 3
    else:
        quality = 2

    question_word = root.question_word
    # Doğru mu?
    if user_answer == correct_answer:
        feedback_label.config(text="Doğru!", fg="green")
        score += 1

        # SM-2 güncelle
        sm2_update(session_words[current_index], quality)
        clear_mistakes_for_word(question_word)
        score_label.config(text=f"Skor: {score}")

        current_index += 1
        root.after(1000, show_question)
    else:
        feedback_label.config(text=f"Yanlış! Doğru cevap: {correct_answer}", fg="red")
        add_to_mistakes(question_word, user_answer, correct_answer)
        # SM-2 güncelle: kalitesi düşük
        sm2_update(session_words[current_index], 1)

        current_index += 1
        root.after(1500, show_question)

# Enter ile cevap kontrolü
root.bind("<Return>", check_answer)

root.mainloop()



