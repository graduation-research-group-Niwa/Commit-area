"""
学習支援パケットアナライザ - キャプチャ種類選択画面
=====================================================

このファイルは「最初にユーザーが見る画面」のUIだけを作ったものです。
Wi-Fi / 有線LAN / ログ読み込み の3種類から選び、インターフェースを選んで
「キャプチャ開始」ボタンを押す、というところまでを作っています。

まだ実際のパケットキャプチャ処理(pyshark等)は入っていません。
下にある on_start_capture() 関数の中身を、後で実際の処理に差し替えれば
そのままアプリとして動く構成にしてあります。

【今回の方針:全画面サイズ固定】
このアプリは全画面専用として使う想定なので、
- 起動時に「今使っているモニターの画面サイズ」を取得する
- そのサイズと、デザインの基準サイズ(BASE_WINDOW_W/H)を比較して
  拡大率(scale)を1回だけ計算する
- 計算した拡大率で全部品(文字・カード・ボタン等)のサイズを決めて配置する
- resizable(False, False) でユーザーがリサイズできないようにする
という作りにしています。ウィンドウリサイズを監視する仕組み(on_resize等)は
不要になったため、前回のバージョンからは削除しています。
"""

import customtkinter

# ------------------------------------------------------------
# 定数まとめ
# ------------------------------------------------------------
FONT_TYPE = "Noto Sans CJK JP"

# デザインを作ったときの「基準サイズ」。
# 実際の画面がこれより大きければ拡大、小さければ縮小、という計算のもとになる。
BASE_WINDOW_W = 760
BASE_WINDOW_H = 620

# 今回のターゲット画面サイズ:フルHD固定。
# 動作させるPCのモニターがフルHD(1920x1080)である前提で、常にこのサイズで
# ウィンドウを開く。モニターがこれより小さい環境で動かすと、ウィンドウが
# 画面からはみ出す点に注意(その場合は自動検出方式に戻すのがおすすめ)。
TARGET_WINDOW_W = 1920
TARGET_WINDOW_H = 1080

# 拡大率の上限・下限(文字が潰れたり間延びしすぎたりしないための保険)
MIN_SCALE = 0.85
MAX_SCALE = 2.2

CAPTURE_TYPES = {
    "wifi": {
        "label": "Wi-Fi",
        "sub_label": "無線LANを監視",
        "icon": "📶",
        "fg_color": "#17293b",
        "circle_color": "#21405c",
        "accent_color": "#4FA8E0",
    },
    "wired": {
        "label": "有線LAN",
        "sub_label": "Ethernetを監視",
        "icon": "🔌",
        "fg_color": "#132922",
        "circle_color": "#1c4536",
        "accent_color": "#3FBF8F",
    },
    "log": {
        "label": "ログ読み込み",
        "sub_label": "既存の記録を解析",
        "icon": "📁",
        "fg_color": "#241a33",
        "circle_color": "#392a54",
        "accent_color": "#9F7FE0",
    },
}

DUMMY_INTERFACES = {
    "wifi": ["Wi-Fi (wlan0)"],
    "wired": ["Ethernet (eth0)", "Ethernet (eth1)"],
    "log": ["ファイルを選択してください..."],
}


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # ---- メンバー変数 ----
        self.selected_type = None
        self.card_widgets = {}

        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("blue")

        # ---- フルHD(1920x1080)を前提に拡大率を1回だけ計算する ----
        scale_w = TARGET_WINDOW_W / BASE_WINDOW_W
        scale_h = TARGET_WINDOW_H / BASE_WINDOW_H
        self.scale = max(MIN_SCALE, min(MAX_SCALE, min(scale_w, scale_h)))

        # ---- ウィンドウをフルHDサイズに固定する ----
        # 実際のモニターサイズ(winfo_screenwidth/height)は、ウィンドウを
        # 画面の真ん中に置くための位置決めにだけ使う。サイズ自体は
        # 1920x1080で固定なので、モニターがフルHDより小さいとウィンドウの
        # 一部が画面からはみ出す点は留意しておくこと。
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = max(0, (screen_w - TARGET_WINDOW_W) // 2)
        pos_y = max(0, (screen_h - TARGET_WINDOW_H) // 2)

        self.geometry(f"{TARGET_WINDOW_W}x{TARGET_WINDOW_H}+{pos_x}+{pos_y}")
        self.resizable(False, False)  # ユーザーによるリサイズを禁止
        self.title("学習パケットアナライザ")

        self.setup_fonts()
        self.setup_form()

    # ------------------------------------------------------------
    # 拡大率(self.scale)を反映したフォントを用意する。
    # ------------------------------------------------------------
    def scaled(self, base_size):
        """基準サイズに拡大率をかけて、整数のフォントサイズを返す小さなヘルパー"""
        return round(base_size * self.scale)

    def setup_fonts(self):
        self.font_title = customtkinter.CTkFont(
            family=FONT_TYPE, size=self.scaled(30), weight="bold"
        )
        self.font_subtitle = customtkinter.CTkFont(
            family=FONT_TYPE, size=self.scaled(16)
        )
        self.font_card_icon = customtkinter.CTkFont(
            family=FONT_TYPE, size=self.scaled(30)
        )
        self.font_card_label = customtkinter.CTkFont(
            family=FONT_TYPE, size=self.scaled(19), weight="bold"
        )
        self.font_card_sub = customtkinter.CTkFont(
            family=FONT_TYPE, size=self.scaled(13)
        )
        self.font_interface_caption = customtkinter.CTkFont(
            family=FONT_TYPE, size=self.scaled(15)
        )
        self.font_interface_menu = customtkinter.CTkFont(
            family=FONT_TYPE, size=self.scaled(16)
        )
        self.font_button = customtkinter.CTkFont(
            family=FONT_TYPE, size=self.scaled(18), weight="bold"
        )

    # ------------------------------------------------------------
    # 画面レイアウトの組み立て
    # ------------------------------------------------------------
    def setup_form(self):
        # 上下の行を weight=1 にして、画面いっぱいのウィンドウの中でも
        # 中身が縦方向の真ん中に来るようにする。
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(8, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- タイトル部分 ---
        title_label = customtkinter.CTkLabel(
            master=self, text="学習パケットアナライザ", font=self.font_title
        )
        title_label.grid(row=1, column=0, pady=(0, self.scaled(8)))

        accent_bar = customtkinter.CTkFrame(
            master=self,
            width=self.scaled(72),
            height=self.scaled(4),
            fg_color="#4FA8E0",
            corner_radius=2,
        )
        accent_bar.grid(row=2, column=0, pady=(0, self.scaled(12)))

        subtitle_label = customtkinter.CTkLabel(
            master=self,
            text="キャプチャの種類を選んでください",
            font=self.font_subtitle,
            text_color="#9AABBD",
        )
        subtitle_label.grid(row=3, column=0, pady=(0, self.scaled(28)))

        # --- 3種類のカード ---
        card_area = customtkinter.CTkFrame(master=self, fg_color="transparent")
        card_area.grid(row=4, column=0, pady=(0, self.scaled(28)))

        for key, info in CAPTURE_TYPES.items():
            card = self.create_card(card_area, key, info)
            card.pack(side="left", padx=self.scaled(16))
            self.card_widgets[key] = card

        # --- インターフェース選択 ---
        interface_frame = customtkinter.CTkFrame(master=self)
        interface_frame.grid(
            row=5,
            column=0,
            sticky="ew",
            padx=self.scaled(50),
            pady=(0, self.scaled(22)),
        )

        interface_caption = customtkinter.CTkLabel(
            master=interface_frame,
            text="対象インターフェース",
            font=self.font_interface_caption,
            text_color="#9AABBD",
        )
        interface_caption.pack(
            anchor="w", padx=self.scaled(16), pady=(self.scaled(14), self.scaled(6))
        )

        self.interface_menu = customtkinter.CTkOptionMenu(
            master=interface_frame,
            values=["種類を選んでください"],
            font=self.font_interface_menu,
            height=self.scaled(46),
        )
        self.interface_menu.pack(
            fill="x", padx=self.scaled(16), pady=(0, self.scaled(16))
        )

        # --- キャプチャ開始ボタン ---
        self.start_button = customtkinter.CTkButton(
            master=self,
            text="▶  キャプチャ開始",
            font=self.font_button,
            height=self.scaled(56),
            corner_radius=12,
            command=self.on_start_capture,
        )
        self.start_button.grid(
            row=6, column=0, sticky="ew", padx=self.scaled(50), pady=(0, 0)
        )

    # ------------------------------------------------------------
    # カード1枚分のウィジェットを作る関数
    # ------------------------------------------------------------
    def create_card(self, parent, key, info):
        card = customtkinter.CTkFrame(
            master=parent,
            width=self.scaled(210),
            height=self.scaled(180),
            corner_radius=16,
            border_width=2,
            border_color="gray30",
            fg_color=info["fg_color"],
        )
        card.pack_propagate(False)

        circle_size = self.scaled(64)
        icon_circle = customtkinter.CTkFrame(
            master=card,
            width=circle_size,
            height=circle_size,
            corner_radius=circle_size // 2,
            fg_color=info["circle_color"],
        )
        icon_circle.pack(pady=(self.scaled(26), self.scaled(10)))
        icon_circle.pack_propagate(False)

        icon_label = customtkinter.CTkLabel(
            master=icon_circle, text=info["icon"], font=self.font_card_icon
        )
        icon_label.place(relx=0.5, rely=0.5, anchor="center")

        label = customtkinter.CTkLabel(
            master=card,
            text=info["label"],
            font=self.font_card_label,
            text_color=info["accent_color"],
        )
        label.pack()

        sub_label = customtkinter.CTkLabel(
            master=card,
            text=info["sub_label"],
            font=self.font_card_sub,
            text_color="#A6B3C2",
        )
        sub_label.pack(pady=(self.scaled(4), 0))

        for widget in (card, icon_circle, icon_label, label, sub_label):
            widget.bind("<Button-1>", lambda event, k=key: self.select_card(k))

        return card

    # ------------------------------------------------------------
    # カードをクリックしたときの処理(選択状態の切り替え)
    # ------------------------------------------------------------
    def select_card(self, key):
        self.selected_type = key

        for card_key, card_widget in self.card_widgets.items():
            if card_key == key:
                accent = CAPTURE_TYPES[card_key]["accent_color"]
                card_widget.configure(border_color=accent, border_width=2)
            else:
                card_widget.configure(border_color="gray30", border_width=2)

        interfaces = DUMMY_INTERFACES.get(key, [])
        self.interface_menu.configure(values=interfaces)
        if interfaces:
            self.interface_menu.set(interfaces[0])

    # ------------------------------------------------------------
    # キャプチャ開始ボタンが押されたときの処理
    # ------------------------------------------------------------
    def on_start_capture(self):
        if self.selected_type is None:
            print("キャプチャの種類が選ばれていません")
            return

        selected_interface = self.interface_menu.get()

        # ==========================================================
        # ここが「後で中身を実装する」ポイント。
        #
        #   import pyshark
        #   capture = pyshark.LiveCapture(interface=selected_interface)
        #   for packet in capture.sniff_continuously():
        #       ...受け取ったpacketを一覧画面に渡す処理...
        #
        # 「ログ読み込み」が選ばれた場合は pyshark.FileCapture(ファイルパス)
        # を使う形になるはず。
        # ==========================================================
        print(f"選択された種類: {self.selected_type}")
        print(f"選択されたインターフェース: {selected_interface}")
        print("※ここに実際のキャプチャ処理を実装していきます")


if __name__ == "__main__":
    app = App()
    app.mainloop()