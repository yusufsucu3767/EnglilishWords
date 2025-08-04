import tkinter as tk
from tkinter import messagebox
import csv
from deep_translator import GoogleTranslator

WORDS_FILE = "words.csv"

def add_word_to_csv(english, turkish, example):
    with open(WORDS_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([english, turkish, example])

def translate_and_save():
    turkish_word = entry_turkish.get().strip()
    if not turkish_word:
        messagebox.showwarning("Uyarı", "Lütfen Türkçe kelime girin!")
        return

    try:
        english_word = GoogleTranslator(source='tr', target='en').translate(turkish_word).lower()
        example_sentence = f"This is a {english_word}."
        add_word_to_csv(english_word, turkish_word, example_sentence)

        messagebox.showinfo("Başarılı", f"Kelime eklendi:\n{english_word} - {turkish_word}\nÖrnek: {example_sentence}")
        entry_turkish.delete(0, tk.END)
    except Exception as e:
        messagebox.showerror("Hata", f"Çeviri sırasında hata oluştu:\n{e}")

# Tkinter arayüzü
root = tk.Tk()
root.title("Kelime Çeviri ve Kaydetme")

tk.Label(root, text="Türkçe Kelime:").pack(pady=5)
entry_turkish = tk.Entry(root, width=40)
entry_turkish.pack(pady=5)
entry_turkish.focus()

btn_translate = tk.Button(root, text="Çevir ve Kaydet", command=translate_and_save)
btn_translate.pack(pady=10)

root.mainloop()


