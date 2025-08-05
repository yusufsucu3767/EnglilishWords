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
import matplotlib.pyplot as plt
from deep_translator import GoogleTranslator

# --- Dosya Yolları ---
WORDS_FILE = "words.csv"
STATS_FILE = "stats.json"
MISTAKES_FILE = "mistakes.txt"

# --- Dracula Tema Renkleri ---
DRACULA_BG      = "#282a36"
DRACULA_FG      = "#f8f8f2"
DRACULA_BTN_BG  = "#44475a"
DRACULA_BTN_FG  = "#f8f8f2"
DRACULA_ACCENT  = "#bd93f9"
DRACULA_ERROR   = "#ff5555"
DRACULA_SUCCESS = "#50fa7b"
DRACULA_LIST_BG = "#44475a"
DRACULA_LIST_FG = "#f8f8f2"

# --- Küresel Değişkenler ---
word_list      = []
stats          = {}
mode           = None
session_words  = []
current_word   = None
score          = 0
start_time     = 0

pygame.mixer.init()

# --- Yardımcı Fonksiyonlar ---
def pronounce(text):
    try:
        t = gTTS(text=text, lang="en")
        buf = BytesIO()
        t.write_to_fp(buf); buf.seek(0)
        pygame.mixer.music.load(buf, "mp3")
        pygame.mixer.music.play()
    except:
        pass

def load_words():
    global word_list
    if not os.path.exists(WORDS_FILE):
        raise RuntimeError(f"{WORDS_FILE} bulunamadı!")
    with open(WORDS_FILE, newline='', encoding='utf-8') as f:
        word_list = [row for row in csv.reader(f) if len(row) >= 3]
    if not word_list:
        raise RuntimeError(f"{WORDS_FILE} boş veya hatalı formatta!")

def load_stats():
    global stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as sf:
                stats = json.load(sf)
        except:
            stats = {}
    else:
        stats = {}

    # Eksik alanları tamamla
    for entry in stats.values():
        entry.setdefault("daily_correct",  0)
        entry.setdefault("daily_wrong",    0)
        entry.setdefault("correct_streak", 0)
        entry.setdefault("interval",       0)
        entry.setdefault("repetitions",    0)
        entry.setdefault("ef",             2.5)
        entry.setdefault("due",            0)

def save_stats():
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

def add_to_mistakes(q, a, c):
    with open(MISTAKES_FILE, "a", encoding="utf-8") as f:
        f.write(f"Soru: {q}\n- Senin cevabın: {a}\n- Doğru: {c}\n\n")

def load_mistakes_words():
    if not os.path.exists(MISTAKES_FILE):
        return []
    with open(MISTAKES_FILE, encoding="utf-8") as f:
        return [l[6:].strip() for l in f if l.startswith("Soru: ")]

def clear_mistakes_for_word(w):
    if not os.path.exists(MISTAKES_FILE):
        return
    import re
    with open(MISTAKES_FILE, encoding="utf-8") as f:
        c = f.read()
    p = re.compile(rf"(Soru: {re.escape(w)}\n(?:-.*\n)*\n)", re.M)
    with open(MISTAKES_FILE, "w", encoding="utf-8") as f:
        f.write(p.sub("", c))

# --- SM-2 Algoritması ---
def sm2_update(word, quality):
    k = word[0]
    if k not in stats:
        stats[k] = {
            "interval": 0, "repetitions": 0, "ef": 2.5, "due": 0,
            "correct_streak": 0, "daily_correct": 0, "daily_wrong": 0
        }
    d = stats[k]

    # Her zaman bu alanlar olsun
    d.setdefault("daily_correct",  0)
    d.setdefault("daily_wrong",    0)
    d.setdefault("correct_streak", 0)

    now = time.time()
    if quality >= 3:
        d["daily_correct"] += 1
        d["correct_streak"] += 1
        if d["repetitions"] == 0:      d["interval"] = 1
        elif d["repetitions"] == 1:    d["interval"] = 6
        else:                          d["interval"] = round(d["interval"] * d["ef"])
        d["repetitions"] += 1
        d["ef"] = max(1.3, d["ef"] + (0.1 - (5-quality)*(0.08 + (5-quality)*0.02)))
        d["due"] = now + d["interval"] * 86400
        if d["correct_streak"] >= 10 and mode != "hardcore" and word in session_words:
            session_words.remove(word)
    else:
        d["daily_wrong"] += 1
        d["correct_streak"] = 0
        d["repetitions"] = 0
        d["interval"] = 1
        d["due"] = now + 86400

# --- Session Oluşturma ---
def create_session():
    global session_words
    now = time.time()
    session_words = []
    if mode == "rutin":
        for w in word_list:
            k = w[0]
            stats.setdefault(k, {"interval":0,"repetitions":0,"ef":2.5,"due":0,"correct_streak":0})
            if stats[k]["due"] <= now:
                session_words.append(w)
        if not session_words:
            messagebox.showinfo("Bilgi", "Bugün tekrar yok!")
            return False
        if len(session_words) > 50:
            session_words = random.sample(session_words, 50)
    elif mode == "hatalar":
        mw = load_mistakes_words()
        session_words = [w for w in word_list if w[0] in mw]
        if not session_words:
            messagebox.showinfo("Bilgi", "Hata modu için kelime yok!")
            return False
    else:  # hardcore
        session_words = word_list.copy()
        if not session_words:
            messagebox.showinfo("Bilgi", "Kelime listesi boş!")
            return False
    return True

# --- Quiz Akışı ---
def show_question():
    global current_word, start_time
    if not session_words:
        messagebox.showinfo("Tebrikler", f"Seans bitti! Skorunuz: {score}")
        save_stats()
        qa_frame.pack_forget()
        menu_frame.pack(padx=30, pady=30)
        return
    idx = random.randrange(len(session_words))
    current_word = session_words.pop(idx)
    eng, tur, ex = current_word
    if random.choice([True, False]):
        question_label.config(text=eng, fg=DRACULA_ACCENT)
        example_label.config(text=ex)
        root.current_answer = tur.lower()
        pronounce(eng)
    else:
        question_label.config(text=tur, fg=DRACULA_ACCENT)
        example_label.config(text="")
        root.current_answer = eng.lower()
    answer_entry.delete(0, tk.END)
    feedback_label.config(text="")
    start_time = time.time()

def check_answer(event=None):
    global score
    ua = answer_entry.get().strip().lower()
    ca = root.current_answer
    dt = time.time() - start_time
    q = 5 if dt<3 else 4 if dt<7 else 3 if dt<12 else 2
    if ua == ca:
        feedback_label.config(text="✅ Doğru!", fg=DRACULA_SUCCESS)
        score += 1
        sm2_update(current_word, q)
    else:
        feedback_label.config(text=f"❌ Yanlış! Doğru: {ca}", fg=DRACULA_ERROR)
        add_to_mistakes(ca, ua, ca)
        sm2_update(current_word, 1)
    score_label.config(text=f"Skor: {score}")
    root.after(800, show_question)

# --- İstatistikler ---
def show_stats():
    dc = sum(v.get("daily_correct",0) for v in stats.values())
    dw = sum(v.get("daily_wrong",0) for v in stats.values())
    tot = len(stats)
    if dc+dw == 0:
        return messagebox.showinfo("İstatistik","Henüz çalışma yok.")
    plt.figure(figsize=(4,4))
    plt.pie([dc, dw],
            labels=["Doğru","Yanlış"],
            colors=[DRACULA_ACCENT, DRACULA_ERROR],
            autopct='%1.1f%%', startangle=140)
    plt.axis('equal'); plt.show()
    messagebox.showinfo("İstatistik",
        f"Toplam kelime: {tot}\nBugün doğru: {dc}\nBugün yanlış: {dw}")

# --- Çok Anlamlı Seçimi ---
def choose_meaning(meanings):
    cw = tk.Toplevel(root)
    cw.title("Anlam Seçimi")
    cw.geometry("320x250"); cw.configure(bg=DRACULA_BG)
    cw.update_idletasks()
    x = (cw.winfo_screenwidth()-cw.winfo_reqwidth())//2
    y = (cw.winfo_screenheight()-cw.winfo_reqheight())//2
    cw.geometry(f"+{x}+{y}")
    tk.Label(cw, text="Anlam seçin:", bg=DRACULA_BG, fg=DRACULA_FG).pack(pady=8)
    lb = tk.Listbox(cw, bg=DRACULA_LIST_BG, fg=DRACULA_LIST_FG,
                    selectbackground=DRACULA_ACCENT, bd=0,
                    highlightthickness=1)
    for m in meanings: lb.insert(tk.END, m)
    lb.pack(padx=15,pady=5,fill=tk.BOTH,expand=True)
    sel = {"v":None}
    def confirm():
        c = lb.curselection()
        if not c: return messagebox.showwarning("Uyarı","Seçim yapın!")
        sel["v"] = lb.get(c[0]); cw.destroy()
    lb.bind("<Return>", lambda e: confirm())
    btnf = tk.Frame(cw, bg=DRACULA_BG); btnf.pack(pady=8)
    tk.Button(btnf, text="Seç", width=10, command=confirm,
              bg=DRACULA_BTN_BG, fg=DRACULA_BTN_FG).pack(side=tk.LEFT,padx=5)
    tk.Button(btnf, text="İptal", width=10, command=cw.destroy,
              bg=DRACULA_BTN_BG, fg=DRACULA_BTN_FG).pack(side=tk.LEFT,padx=5)
    lb.selection_set(0); lb.activate(0)
    cw.transient(root); cw.grab_set(); root.wait_window(cw)
    return sel["v"]

# --- Kelime Ekleme ---
def add_word_ui():
    aw = tk.Toplevel(root); aw.title("Kelime Ekle"); aw.configure(bg=DRACULA_BG)
    tk.Label(aw, text="Türkçe kelime:", bg=DRACULA_BG, fg=DRACULA_FG).pack(pady=8)
    e = tk.Entry(aw, bg=DRACULA_LIST_BG, fg=DRACULA_LIST_FG)
    e.pack(pady=5); e.focus_set()
    def go():
        t = e.get().strip()
        if not t: return messagebox.showwarning("Uyarı","Gir!")
        try:
            tr = GoogleTranslator(source='tr', target='en').translate(t)
            ml = [m.strip() for m in tr.replace(";",",").split(",")] if "," in tr else [tr]
            cm = choose_meaning(ml) if len(ml)>1 else ml[0]
            ex = f"This is a {cm}."
        except Exception as x:
            return messagebox.showerror("Hata", x)
        if any(w[0].lower()==cm.lower() for w in word_list):
            return messagebox.showinfo("Bilgi","Zaten var!")
        with open(WORDS_FILE,"a",encoding="utf-8",newline="") as f:
            csv.writer(f).writerow([cm, t, ex])
        word_list.append([cm, t, ex])
        messagebox.showinfo("Başarılı",f"{t} eklendi"); e.delete(0, tk.END)
    tk.Button(aw, text="Ekle", command=go,
              bg=DRACULA_BTN_BG, fg=DRACULA_BTN_FG).pack(pady=6)
    tk.Button(aw, text="Kapat", command=aw.destroy,
              bg=DRACULA_BTN_BG, fg=DRACULA_BTN_FG).pack(pady=4)
    aw.transient(root); aw.grab_set(); root.wait_window(aw)

# --- Ana Arayüz ---
root = tk.Tk(); root.title("İngilizce Kelime Öğrenme"); root.configure(bg=DRACULA_BG)
menu_frame = tk.Frame(root, bg=DRACULA_BG); menu_frame.pack(padx=30,pady=30)
tk.Label(menu_frame, text="Mod Seçimi", font=("Arial",18),
         bg=DRACULA_BG, fg=DRACULA_ACCENT).pack(pady=10)
for txt, cmd in [
    ("Günlük Rutin",  lambda: m_start("rutin")),
    ("Hatalar Modu",  lambda: m_start("hatalar")),
    ("Hardcore Mod",  lambda: m_start("hardcore")),
    ("Kelime Ekle",   add_word_ui),
    ("İstatistikler", show_stats),
]:
    tk.Button(menu_frame, text=txt, width=20, command=cmd,
              bg=DRACULA_BTN_BG, fg=DRACULA_BTN_FG).pack(pady=4)

qa_frame = tk.Frame(root, bg=DRACULA_BG)
question_label = tk.Label(qa_frame, text="", font=("Arial",20),
                          bg=DRACULA_BG, fg=DRACULA_ACCENT); question_label.pack(pady=10)
example_label = tk.Label(qa_frame, text="", font=("Arial",14),
                         bg=DRACULA_BG, fg="#6272a4"); example_label.pack(pady=4)
answer_entry = tk.Entry(qa_frame, font=("Arial",16),
                        bg=DRACULA_LIST_BG, fg=DRACULA_LIST_FG); answer_entry.pack(pady=8)
answer_entry.bind("<Return>", check_answer)
feedback_label = tk.Label(qa_frame, text="", font=("Arial",14),
                          bg=DRACULA_BG, fg=DRACULA_FG); feedback_label.pack(pady=4)
score_label = tk.Label(qa_frame, text="Skor: 0", font=("Arial",14),
                       bg=DRACULA_BG, fg=DRACULA_FG); score_label.pack(pady=4)

def m_start(m):
    global mode, score
    mode = m; score = 0
    load_stats()
    if create_session():
        menu_frame.pack_forget()
        qa_frame.pack(padx=30, pady=30)
        show_question()

# --- Başlat ---
load_words()
load_stats()
root.mainloop()
