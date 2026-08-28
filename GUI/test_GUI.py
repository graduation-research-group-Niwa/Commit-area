import customtkinter as ctk

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("パケットキャプチャアプリ")
        self.geometry("600x400")

        self.label =  ctk.CTkLabel(self, text="Hello, UI!")
        self.label.pack(pady=20)

        self.button = ctk.CTkButton(self, text="押してみて", command=self.on_click)
        self.button.pack(pady=10)

    def on_click(self):
        self.label.configure(text="ボタンが押されたよ！")

if __name__ == "__main__":
    app =App()
    app.mainloop()