import csv
import json
import os
import random
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog
from gtts import gTTS
from io import BytesIO
import pygame
from deep_translator import GoogleTranslator

# --- DOSYA YOLLARI ---
WORDS_FILE = "words.csv"
STATS_FILE = "stats.json"
MISTAKES_FILE = "mistakes.txt"

# --- GLOBALLER ---
word_list = []       # (eng, tur, example)
stats = {}
mode = None
session_words = []
current_index = 0
start_time = 0
score = 0

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
        # Boş dosya oluştur
        with open(WORDS_FILE, "w", encoding="utf-8", newline="") as f:
            pass
    with open(WORDS_FILE, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        word_list.clear()
        for row in reader:
            if len(row) >= 3:
                word_list.append((row[0], row[1], row[2]))

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

# --- MISTAKES ---
def add_to_mistakes(question, your_answer, correct_answer):
    with open(MISTAKES_FILE, "a", encoding="utf-8") as mf:
        mf.write(f"Soru: {question}\n")
        mf.write(f"- Senin cevabın: {your_answer}\n")
        mf.write(f"- Doğru cevap: {correct_answer}\n\n")

def load_mistakes_words():
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
    if not os.path.exists(MISTAKES_FILE):
        return
    import re
    with open(MISTAKES_FILE, encoding="utf-8") as mf:
        content = mf.read()
    pattern = re.compile(rf"(Soru: {re.escape(word)}\n(?:-.*\n)*\n)", re.MULTILINE)
    content_new = pattern.sub("", content)
    with open(MISTAKES_FILE, "w", encoding="utf-8") as mf:
        mf.write(content_new)

# --- SESSION OLUŞTURMA ---
def create_session():
    global session_words
    if mode == "rutin":
        session_words = []
        now = time.time()
        for w in word_list:
            key = w[0]
            if key not in stats:
                stats[key] = {"interval": 0, "repetitions": 0, "ef": 2.5, "due": 0, "correct_streak": 0}
            if stats[key]["due"] <= now:
                session_words.append(w)
        if not session_words:
            messagebox.showinfo("Bilgi", "Bugün tekrar edilmesi gereken kelime yok!")
            return False
        if len(session_words) > 50:
            session_words = random.sample(session_words, 50)

    elif mode == "hatalar":
        mistake_words = load_mistakes_words()
        session_words = [w for w in word_list if w[0] in mistake_words]
        if not session_words:
            messagebox.showinfo("Bilgi", "Hata oranı yüksek kelime yok!")
            return False

    elif mode == "hardcore":
        session_words = word_list.copy()
        if not session_words:
            messagebox.showinfo("Bilgi", "Kelime listesi boş!")
            return False

    random.shuffle(session_words)
    return True

# --- SM-2 ALGORİTMASI ---
def sm2_update(word, quality):
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
        data["correct_streak"] += 1
        # 10 kere üst üste doğruysa hardcore hariç listeden çıkar
        if data["correct_streak"] >= 10 and mode != "hardcore":
            if word in session_words:
                session_words.remove(word)
    else:
        data["repetitions"] = 0
        data["interval"] = 1
        data["due"] = time.time() + 24 * 3600
        data["correct_streak"] = 0

# --- ANA PENCERE ---
root = tk.Tk()
root.title("İngilizce Kelime Öğrenme")
root.geometry("500x350")

# --- Ana Menü ---
def start_mode(selected_mode):
    global mode, current_index, score
    mode = selected_mode
    current_index = 0
    score = 0
    if not create_session():
        return
    main_menu_frame.pack_forget()
    session_frame.pack(fill="both", expand=True)
    show_question()

# --- Ana Menü Frame ---
main_menu_frame = tk.Frame(root)
main_menu_frame.pack(fill="both", expand=True)

tk.Label(main_menu_frame, text="Kelime Öğrenme Uygulaması", font=("Arial", 18)).pack(pady=15)

tk.Button(main_menu_frame, text="Günlük Rutin Modu", font=("Arial", 14),
          command=lambda: start_mode("rutin")).pack(pady=5, fill="x", padx=100)
tk.Button(main_menu_frame, text="Hatalar Modu", font=("Arial", 14),
          command=lambda: start_mode("hatalar")).pack(pady=5, fill="x", padx=100)
tk.Button(main_menu_frame, text="Hardcore Mod", font=("Arial", 14),
          command=lambda: start_mode("hardcore")).pack(pady=5, fill="x", padx=100)
tk.Button(main_menu_frame, text="Kelime Ekle", font=("Arial", 14),
          command=lambda: show_add_word_window()).pack(pady=20, fill="x", padx=100)

# --- Çalışma Frame ---
session_frame = tk.Frame(root)

question_label = tk.Label(session_frame, text="", font=("Arial", 20))
question_label.pack(pady=15)

example_label = tk.Label(session_frame, text="", font=("Arial", 14), fg="gray")
example_label.pack(pady=5)

answer_entry = tk.Entry(session_frame, font=("Arial", 16))
answer_entry.pack(pady=15)
answer_entry.focus_set()

feedback_label = tk.Label(session_frame, text="", font=("Arial", 16))
feedback_label.pack(pady=10)

score_label = tk.Label(session_frame, text="Skor: 0", font=("Arial", 16))
score_label.pack(pady=5)

back_to_menu_btn = tk.Button(session_frame, text="Ana Menüye Dön", command=lambda: back_to_menu())
back_to_menu_btn.pack(pady=10)

def show_question():
    global current_index, start_time
    if current_index >= len(session_words):
        messagebox.showinfo("Tebrikler!", f"Seans bitti! Toplam skor: {score}")
        save_stats()
        back_to_menu()
        return
    eng, tur, example = session_words[current_index]

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
    global current_index, score
    user_answer = answer_entry.get().strip().lower()
    correct_answer = root.current_answer
    time_taken = time.time() - start_time

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

root.bind("<Return>", check_answer)

def back_to_menu():
    session_frame.pack_forget()
    main_menu_frame.pack(fill="both", expand=True)
    load_words()
    load_stats()

# --- KELİME EKLEME EKRANI ---
def show_add_word_window():
    add_window = tk.Toplevel(root)
    add_window.title("Kelime Ekle")
    add_window.geometry("400x250")

    tk.Label(add_window, text="Türkçe Kelime Girin:", font=("Arial", 14)).pack(pady=10)
    tur_entry = tk.Entry(add_window, font=("Arial", 14))
    tur_entry.pack(pady=10)
    tur_entry.focus_set()

    output_label = tk.Label(add_window, text="", font=("Arial", 12), fg="blue")
    output_label.pack(pady=5)

    def add_word_action():
        tur_word = tur_entry.get().strip()
        if not tur_word:
            messagebox.showerror("Hata", "Türkçe kelime boş olamaz!")
            return
        # İngilizce ve örnek cümleyi bul
        try:
            eng_word = GoogleTranslator(source="tr", target="en").translate(tur_word)
            example_sentence = GoogleTranslator(source="en", target="en").translate(f"This is a {eng_word}.")
        except Exception as e:
            messagebox.showerror("Hata", f"Çeviri hatası: {e}")
            return

        # Kaydet
        with open(WORDS_FILE, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([eng_word, tur_word, example_sentence])

        output_label.config(text=f"Kelime eklendi:\n{eng_word} - {tur_word}")
        tur_entry.delete(0, tk.END)

        # Listeyi yenile
        load_words()
        load_stats()

    add_btn = tk.Button(add_window, text="Kelime Ekle", command=add_word_action)
    add_btn.pack(pady=10)

    def close_window():
        add_window.destroy()

    back_btn = tk.Button(add_window, text="Ana Menüye Dön", command=close_window)
    back_btn.pack(pady=10)

# --- PROGRAM BAŞLANGICI ---
load_words()
load_stats()
root.mainloop()
