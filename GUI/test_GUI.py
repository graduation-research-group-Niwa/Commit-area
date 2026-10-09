"""
学習パケットアナライザ - 統合版
================================
タイトル画面(キャプチャ種類の選択)と、パケット一覧画面を
1つのウィンドウの中で切り替えるアプリ。

構成:
  App           ... ウィンドウ本体。2つの画面を持ち、切り替える。
                    キャプチャ処理との接続口(set_handlers / packet_queue)もここ。
  TitleScreen   ... 最初の画面(種類とインターフェースの選択)
  CaptureScreen ... パケット一覧・詳細・状態表示の画面
  DummyCapture  ... チームのキャプチャ処理の代役(本物ができたら差し替える)

画面の流れ:
  TitleScreen で「キャプチャ開始」
      -> App.show_capture(種類, インターフェース)
      -> CaptureScreen に切り替わり、自動でキャプチャ開始
  CaptureScreen の「戻る」
      -> キャプチャ停止 -> TitleScreen に戻る
"""

import queue
import random
import threading
from datetime import datetime
from tkinter import ttk

import customtkinter

# ------------------------------------------------------------
# 定数まとめ
# ------------------------------------------------------------
FONT_TYPE = "Noto Sans CJK JP"

# デザインを作ったときの「基準サイズ」。
BASE_WINDOW_W = 760
BASE_WINDOW_H = 620

# ターゲット画面サイズ:フルHD固定。
TARGET_WINDOW_W = 1920
TARGET_WINDOW_H = 1080

# 拡大率の上限・下限
MIN_SCALE = 0.85
MAX_SCALE = 2.2

# パケット一覧(Treeview)の文字サイズと行の高さの「基準値」。
# 実際に見て大きすぎ/小さすぎたら、ここの数字を変えて調整する。
TREE_FONT_BASE = 8
TREE_ROW_BASE = 20

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


# ============================================================
# 画面1: タイトル画面(キャプチャ種類の選択)
# ============================================================
class TitleScreen(customtkinter.CTkFrame):
    def __init__(self, master, ui_scale, on_start):
        # fg_color="transparent" にして、ウィンドウの背景色と同じ見た目にする
        super().__init__(master, fg_color="transparent")

        self.ui_scale = ui_scale
        self.on_start = on_start  # (種類, インターフェース) を受け取る関数。Appが渡してくる
        self.selected_type = None
        self.card_widgets = {}

        self.setup_fonts()
        self.setup_form()

    # ------------------------------------------------------------
    # 拡大率を反映したフォントを用意する。
    # ------------------------------------------------------------
    def scaled(self, base_size):
        """基準サイズに拡大率をかけて、整数のサイズを返す小さなヘルパー"""
        return round(base_size * self.ui_scale)

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
        # 上下の行を weight=1 にして、中身が縦方向の真ん中に来るようにする。
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

        # 実際の画面切り替えとキャプチャ開始は App 側がやる。
        # (「ログ読み込み」のときのファイル選択などは、今後ここで追加する)
        self.on_start(self.selected_type, selected_interface)


# ============================================================
# 画面2: パケット一覧画面
# ============================================================
class CaptureScreen(customtkinter.CTkFrame):
    def __init__(self, master, ui_scale, packet_queue, on_start, on_stop, on_back):
        super().__init__(master, fg_color="transparent")

        self.ui_scale = ui_scale
        self.packet_queue = packet_queue
        self.on_start_callback = on_start  # (種類, インターフェース, フィルタ文字列)
        self.on_stop_callback = on_stop    # 引数なし
        self.on_back_callback = on_back    # 引数なし

        self.capture_type = None
        self.interface = None
        self.details = {}  # 行の番号 -> 詳細テキスト

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)  # 一覧エリア(大きめ)
        self.grid_rowconfigure(2, weight=1)  # 詳細エリア(小さめ)

        self.setup_fonts()
        self.create_toolbar()
        self.create_packet_list()
        self.create_detail_pane()
        self.create_statusbar()

        # 0.1秒ごとにキューを確認し始める(以降、自分で繰り返す)
        self.after(100, self.process_queue)

    def scaled(self, base_size):
        return round(base_size * self.ui_scale)

    def setup_fonts(self):
        self.font_button = customtkinter.CTkFont(
            family=FONT_TYPE, size=self.scaled(15), weight="bold"
        )
        self.font_body = customtkinter.CTkFont(
            family=FONT_TYPE, size=self.scaled(14)
        )

    # ========== 画面の部品を作るメソッド ==========
    def create_toolbar(self):
        self.toolbar = customtkinter.CTkFrame(self)
        self.toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        self.back_button = customtkinter.CTkButton(
            self.toolbar,
            text="◀ 戻る",
            font=self.font_button,
            height=self.scaled(40),
            width=self.scaled(100),
            fg_color="gray30",
            hover_color="gray40",
            command=self.go_back,
        )
        self.back_button.pack(side="left", padx=5, pady=5)

        self.start_button = customtkinter.CTkButton(
            self.toolbar,
            text="開始",
            font=self.font_button,
            height=self.scaled(40),
            command=self.start_capture,
        )
        self.start_button.pack(side="left", padx=5, pady=5)

        self.stop_button = customtkinter.CTkButton(
            self.toolbar,
            text="停止",
            font=self.font_button,
            height=self.scaled(40),
            command=self.stop_capture,
        )
        self.stop_button.pack(side="left", padx=5, pady=5)

        self.filter_entry = customtkinter.CTkEntry(
            self.toolbar,
            placeholder_text="フィルタ（例: tcp, port 80）",
            font=self.font_body,
            height=self.scaled(40),
        )
        self.filter_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)

    def create_packet_list(self):
        self.main_frame = customtkinter.CTkFrame(self)
        self.main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.setup_treeview_style()

        columns = ("No", "Time", "src", "dst", "Protocol")
        self.tree = ttk.Treeview(self.main_frame, columns=columns, show="headings")

        self.tree.heading("No", text="No.")
        self.tree.heading("Time", text="時刻")
        self.tree.heading("src", text="送信元")
        self.tree.heading("dst", text="宛先")
        self.tree.heading("Protocol", text="プロトコル")

        self.tree.column("No", width=self.scaled(60), anchor="center")
        self.tree.column("Time", width=self.scaled(150))
        self.tree.column("src", width=self.scaled(150))
        self.tree.column("dst", width=self.scaled(150))
        self.tree.column("Protocol", width=self.scaled(100), anchor="center")

        self.tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            self.main_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # 行が選ばれたときに on_select を呼ぶ
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def create_detail_pane(self):
        self.detail_box = customtkinter.CTkTextbox(self, font=self.font_body)
        self.detail_box.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        self.detail_box.configure(state="disabled")  # 読み取り専用

    def create_statusbar(self):
        self.status_label = customtkinter.CTkLabel(
            self, text="状態: 停止中", anchor="w", font=self.font_body
        )
        self.status_label.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

    def setup_treeview_style(self):
        font_size = self.scaled(TREE_FONT_BASE)
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#2a2d2e",
            foreground="white",
            fieldbackground="#2a2d2e",
            rowheight=self.scaled(TREE_ROW_BASE),
            borderwidth=0,
            font=(FONT_TYPE, font_size),
        )
        style.configure(
            "Treeview.Heading",
            background="#565b5e",
            foreground="white",
            borderwidth=0,
            font=(FONT_TYPE, font_size, "bold"),
        )
        style.map("Treeview", background=[("selected", "#22559b")])

    # ========== 開始・停止・戻る ==========
    def begin(self, capture_type, interface):
        """この画面に切り替わったときに App から呼ばれる。選択内容を覚えて、すぐ開始する"""
        self.capture_type = capture_type
        self.interface = interface
        self.start_capture()

    def start_capture(self):
        self.clear_packets()
        self.update_status(running=True)
        self.on_start_callback(
            self.capture_type, self.interface, self.filter_entry.get()
        )

    def stop_capture(self):
        self.update_status(running=False)
        self.on_stop_callback()

    def go_back(self):
        self.stop_capture()
        self.on_back_callback()

    def update_status(self, running):
        """状態表示と、ボタンの押せる/押せないを切り替える"""
        state_text = "キャプチャ中" if running else "停止中"
        info = CAPTURE_TYPES.get(self.capture_type, {}).get("label", "")
        self.status_label.configure(
            text=f"状態: {state_text}　|　{info}: {self.interface}"
        )
        # キャプチャ中は「開始」を押せなくする(二重開始の防止)
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")

    # ========== 一覧の操作(UIの流れの中だけで呼ぶ) ==========
    def add_packet(self, no, time, src, dst, protocol, detail=""):
        """パケット1件を一覧に追加する"""
        iid = str(no)
        self.tree.insert("", "end", iid=iid, values=(no, time, src, dst, protocol))
        self.details[iid] = detail
        self.tree.see(iid)  # 常に最新の行までスクロール

    def clear_packets(self):
        """一覧を空にする。キューに残っている古いパケットも捨てる"""
        self.tree.delete(*self.tree.get_children())
        self.details.clear()
        while True:
            try:
                self.packet_queue.get_nowait()
            except queue.Empty:
                break

    def process_queue(self):
        """キューに溜まったパケットを全部取り出して表示する。0.1秒ごとに自分で再実行"""
        try:
            while True:
                packet = self.packet_queue.get_nowait()
                self.add_packet(**packet)
        except queue.Empty:
            pass
        finally:
            # 途中でエラーが起きても、次の確認はちゃんと予約する
            self.after(100, self.process_queue)

    # ========== 行を選んだときの処理 ==========
    def on_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        text = self.details.get(selected[0], "")

        self.detail_box.configure(state="normal")
        self.detail_box.delete("1.0", "end")
        self.detail_box.insert("1.0", text)
        self.detail_box.configure(state="disabled")


# ============================================================
# ウィンドウ本体
# ============================================================
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("blue")

        # ---- フルHDを前提に拡大率を1回だけ計算する ----
        scale_w = TARGET_WINDOW_W / BASE_WINDOW_W
        scale_h = TARGET_WINDOW_H / BASE_WINDOW_H
        self.ui_scale = max(MIN_SCALE, min(MAX_SCALE, min(scale_w, scale_h)))

        # ---- ウィンドウをフルHDサイズに固定して、画面の真ん中に置く ----
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = max(0, (screen_w - TARGET_WINDOW_W) // 2)
        pos_y = max(0, (screen_h - TARGET_WINDOW_H) // 2)

        self.geometry(f"{TARGET_WINDOW_W}x{TARGET_WINDOW_H}+{pos_x}+{pos_y}")
        self.resizable(False, False)
        self.title("学習パケットアナライザ")

        # ---- キャプチャ処理との接続口 ----
        self.packet_queue = queue.Queue()  # キャプチャ側はここに put する
        self.on_start_callback = None
        self.on_stop_callback = None

        # ---- 2つの画面を作る(同じ場所に重ねて、片方だけ表示する) ----
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.title_screen = TitleScreen(
            self, self.ui_scale, on_start=self.show_capture
        )
        self.capture_screen = CaptureScreen(
            self,
            self.ui_scale,
            self.packet_queue,
            on_start=self._handle_start,
            on_stop=self._handle_stop,
            on_back=self.show_title,
        )

        self.show_title()

    # ========== 画面の切り替え ==========
    def _show(self, screen):
        self.title_screen.grid_forget()
        self.capture_screen.grid_forget()
        screen.grid(row=0, column=0, sticky="nsew")

    def show_title(self):
        self._show(self.title_screen)

    def show_capture(self, capture_type, interface):
        self._show(self.capture_screen)
        self.capture_screen.begin(capture_type, interface)

    # ========== チームとの接続口 ==========
    def set_handlers(self, on_start, on_stop):
        """開始/停止のときに呼ぶ関数を登録する

        on_start(capture_type, interface, filter_text)
        on_stop()
        """
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop

    def _handle_start(self, capture_type, interface, filter_text):
        if self.on_start_callback:
            self.on_start_callback(capture_type, interface, filter_text)

    def _handle_stop(self):
        if self.on_stop_callback:
            self.on_stop_callback()


# ============================================================
# チームの代役(あとで本物に差し替える)
# ============================================================
class DummyCapture:
    def __init__(self, packet_queue):
        self.packet_queue = packet_queue
        self._stop_event = None

    def start(self, capture_type, interface, filter_text=""):
        # すでに動いているなら何もしない
        if self._stop_event is not None and not self._stop_event.is_set():
            return
        # 開始のたびに新しい「止めるための旗」を作る。
        # 古いスレッドは古い旗で止まるので、素早く停止→開始しても混ざらない。
        self._stop_event = threading.Event()
        threading.Thread(
            target=self._run,
            args=(self._stop_event, capture_type, interface),
            daemon=True,
        ).start()

    def stop(self):
        if self._stop_event is not None:
            self._stop_event.set()

    def _run(self, stop_event, capture_type, interface):
        no = 1
        while not stop_event.is_set():
            protocol = random.choice(["TCP", "UDP", "DNS", "TLS"])
            packet = {
                "no": no,
                "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "src": f"192.168.1.{random.randint(2, 50)}",
                "dst": f"10.0.0.{random.randint(2, 50)}",
                "protocol": protocol,
                "detail": (
                    f"{protocol} パケット\n"
                    f"  番号: {no}\n"
                    f"  キャプチャ種類: {capture_type}\n"
                    f"  インターフェース: {interface}"
                ),
            }
            self.packet_queue.put(packet)  # 画面は触らず、キューに入れるだけ
            no += 1
            stop_event.wait(0.5)  # 0.5秒待つ。stop されたらすぐ起きる


if __name__ == "__main__":
    app = App()
    capture = DummyCapture(app.packet_queue)
    app.set_handlers(on_start=capture.start, on_stop=capture.stop)
    app.mainloop()