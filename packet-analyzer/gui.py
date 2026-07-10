"""
gui.py
CustomTkinterによるデスクトップアプリケーション画面

役割:
  - パケット一覧のリアルタイム表示
  - パケット詳細の表示（学習支援解説つき）
  - プロトコル割合グラフの表示
  - キャプチャの開始・停止、pcap保存・読み込み

注意:
  CustomTkinterはボタン・ラベル・入力欄など「見た目」に関わる部分を担当する。
  一覧表（Treeview）はCustomTkinterに専用ウィジェットがないため、
  標準Tkinter(ttk)のTreeviewをそのまま使い、スタイルだけ合わせている。
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from collections import Counter

import customtkinter as ctk

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from analyzer import PacketAnalyzer
from explanations import FIELD_EXPLANATIONS, get_flag_explanations, get_port_explanation

# CustomTkinterの見た目設定（アプリ起動前に一度だけ行う）
ctk.set_appearance_mode("light")       # "light" / "dark" / "system"
ctk.set_default_color_theme("blue")    # ボタンなどのアクセントカラー


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Packet Analyzer - Protocol Learning Tool")
        self.geometry("1080x680")
        self.minsize(900, 560)

        # 日本語表示のためのフォント設定
        self._setup_fonts()

        self.analyzer = PacketAnalyzer()
        self.packets: list[dict] = []
        self.proto_counter = Counter()
        self._poll_job = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_queue()

    # ------------------------------------------------------------------
    # フォント設定
    # ------------------------------------------------------------------
    def _setup_fonts(self):
        """環境に応じて日本語表示可能なフォントを選び、CTkFontとして用意する"""
        import tkinter.font as tkfont

        available = set(tkfont.families())
        candidates = [
            "Yu Gothic UI", "Yu Gothic", "Meiryo UI", "Meiryo",
            "MS Gothic", "Noto Sans CJK JP", "Takao Gothic", "IPAGothic",
        ]
        family = next((f for f in candidates if f in available), None)
        self.jp_font_family = family or "TkDefaultFont"

        # CustomTkinterのウィジェットは各自にフォントを渡す必要があるため、
        # 用途別にCTkFontインスタンスを作っておき、以降はこれを使い回す
        self.font_normal = ctk.CTkFont(family=self.jp_font_family, size=13)
        self.font_bold = ctk.CTkFont(family=self.jp_font_family, size=13, weight="bold")
        self.font_heading = ctk.CTkFont(family=self.jp_font_family, size=15, weight="bold")
        self.font_mono = ctk.CTkFont(family=self.jp_font_family, size=12)

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------
    def _build_ui(self):
        self._build_toolbar()

        # 左右分割はCustomTkinterに専用ウィジェットがないため、
        # 標準TkinterのPanedWindowをそのまま使い、中身をCTkFrameにする
        pane = tk.PanedWindow(self, orient="horizontal", sashwidth=6, bg="#dbdbdb")
        pane.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        left = ctk.CTkFrame(pane, corner_radius=8)
        pane.add(left, minsize=480)
        self._build_packet_table(left)

        right = ctk.CTkFrame(pane, corner_radius=8, width=340)
        pane.add(right, minsize=300)
        self._build_detail_panel(right)

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=(10, 4))

        self.btn_start = ctk.CTkButton(
            bar, text="\u25b6 開始", width=90, font=self.font_normal, command=self._start,
        )
        self.btn_start.pack(side="left", padx=(0, 6))

        self.btn_stop = ctk.CTkButton(
            bar, text="\u25a0 停止", width=90, font=self.font_normal, command=self._stop,
            state="disabled", fg_color="#B4433B", hover_color="#8F332C",
        )
        self.btn_stop.pack(side="left", padx=6)

        ctk.CTkFrame(bar, width=2, height=28, fg_color="#d0d0d0").pack(side="left", padx=10)

        ctk.CTkButton(
            bar, text="pcap保存", width=90, font=self.font_normal,
            fg_color="#5A5A5A", hover_color="#454545", command=self._save_pcap,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            bar, text="pcap読込", width=90, font=self.font_normal,
            fg_color="#5A5A5A", hover_color="#454545", command=self._load_pcap,
        ).pack(side="left", padx=6)

        ctk.CTkFrame(bar, width=2, height=28, fg_color="#d0d0d0").pack(side="left", padx=10)

        ctk.CTkLabel(bar, text="フィルタ:", font=self.font_normal).pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._apply_filter())
        ctk.CTkEntry(
            bar, textvariable=self.filter_var, width=160, font=self.font_normal,
            placeholder_text="IP・ポートで検索",
        ).pack(side="left", padx=6)

        self.proto_filter_var = tk.StringVar(value="すべて")
        ctk.CTkComboBox(
            bar, variable=self.proto_filter_var, width=100, font=self.font_normal,
            values=["すべて", "TCP", "UDP", "OTHER"],
            command=lambda _v: self._apply_filter(),
            state="readonly",
        ).pack(side="left", padx=6)

        self.status_var = tk.StringVar(value="待機中")
        ctk.CTkLabel(
            bar, textvariable=self.status_var, font=self.font_normal, text_color="#888888",
        ).pack(side="right", padx=4)

    def _build_packet_table(self, parent):
        # Treeviewはttkウィジェットのため、CTkのテーマではなく
        # ttk.Styleで見た目をCustomTkinter風に近づける
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            font=(self.jp_font_family, 11),
            rowheight=24,
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            font=(self.jp_font_family, 11, "bold"),
            background="#F0F0F0",
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#3B8ED0")], foreground=[("selected", "#FFFFFF")])

        table_frame = ctk.CTkFrame(parent, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=8, pady=8)

        cols = ("no", "time", "src", "dst", "proto", "flags", "ttl", "len")
        headers = {
            "no": "No", "time": "時刻", "src": "送信元IP", "dst": "宛先IP",
            "proto": "種別", "flags": "Flags", "ttl": "TTL", "len": "Len",
        }
        widths = {
            "no": 40, "time": 90, "src": 130, "dst": 130,
            "proto": 50, "flags": 90, "ttl": 40, "len": 50,
        }

        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=24)
        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c], anchor="center" if c not in ("src", "dst") else "w")
        self.tree.pack(fill="both", expand=True, side="left")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        self.tree.tag_configure("TCP", background="#EAF2FB")
        self.tree.tag_configure("UDP", background="#E7F6EF")
        self.tree.tag_configure("OTHER", background="#F2F2F2")

    def _build_detail_panel(self, parent):
        ctk.CTkLabel(
            parent, text="パケット詳細", font=self.font_heading, anchor="w",
        ).pack(fill="x", padx=8, pady=(8, 4))

        self.detail_text = ctk.CTkTextbox(
            parent, height=340, font=self.font_mono, wrap="word",
            state="disabled", corner_radius=6,
        )
        self.detail_text.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkLabel(
            parent, text="プロトコル割合", font=self.font_heading, anchor="w",
        ).pack(fill="x", padx=8, pady=(4, 4))

        chart_frame = ctk.CTkFrame(parent, fg_color="transparent")
        chart_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.fig, self.ax = plt.subplots(figsize=(3.2, 2.6))
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack()
        self._update_chart()

    # ------------------------------------------------------------------
    # キャプチャ制御
    # ------------------------------------------------------------------
    def _start(self):
        self.analyzer.start()
        self.status_var.set("\u25cf キャプチャ中")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

    def _stop(self):
        self.analyzer.stop()
        self.status_var.set("停止")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def _save_pcap(self):
        if not self.analyzer.raw_packets:
            messagebox.showinfo("pcap保存", "保存するパケットがありません")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pcap",
            filetypes=[("pcap files", "*.pcap"), ("all files", "*.*")],
        )
        if not filepath:
            return
        count = self.analyzer.save_pcap(filepath)
        messagebox.showinfo("pcap保存", f"{count}件のパケットを保存しました")

    def _load_pcap(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("pcap files", "*.pcap *.pcapng"), ("all files", "*.*")],
        )
        if not filepath:
            return
        try:
            parsed_list = self.analyzer.load_pcap(filepath)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("pcap読込エラー", str(e))
            return

        self.tree.delete(*self.tree.get_children())
        self.packets.clear()
        self.proto_counter.clear()
        for pkt in parsed_list:
            self._add_row(pkt)
        self.status_var.set(f"pcap読込完了（{len(parsed_list)}件）")

    # ------------------------------------------------------------------
    # キュー監視 / 行追加
    # ------------------------------------------------------------------
    def _poll_queue(self):
        try:
            while True:
                pkt = self.analyzer.packet_queue.get_nowait()
                if "error" in pkt:
                    self.status_var.set(pkt["error"])
                    self._stop()
                    continue
                self._add_row(pkt)
        except Exception:
            pass
        self._poll_job = self.after(150, self._poll_queue)

    def _on_close(self):
        """ウィンドウを閉じる際の後片付け"""
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        self.analyzer.stop()
        self.destroy()
        # daemonスレッド(Scapyのキャプチャ)がすぐに終わらない場合があるため、
        # ウィンドウを破棄したらプロセスも明示的に終了させる
        os._exit(0)

    def _add_row(self, pkt: dict):
        self.packets.append(pkt)
        proto = pkt.get("proto", "OTHER")
        self.tree.insert(
            "", "end", iid=str(len(self.packets) - 1),
            values=(
                pkt.get("no", "-"),
                pkt.get("time", "-"),
                pkt.get("ip_src", "-"),
                pkt.get("ip_dst", "-"),
                proto,
                pkt.get("flags", "-"),
                pkt.get("ttl", "-"),
                pkt.get("length", "-"),
            ),
            tags=(proto,),
        )
        self.tree.yview_moveto(1)
        self.proto_counter[proto] += 1
        self._update_chart()

    # ------------------------------------------------------------------
    # フィルタ
    # ------------------------------------------------------------------
    def _apply_filter(self):
        keyword = self.filter_var.get().strip().lower()
        proto_filter = self.proto_filter_var.get()

        self.tree.delete(*self.tree.get_children())
        for idx, pkt in enumerate(self.packets):
            if proto_filter != "すべて" and pkt.get("proto") != proto_filter:
                continue
            haystack = f"{pkt.get('ip_src','')} {pkt.get('ip_dst','')} {pkt.get('sport','')} {pkt.get('dport','')}".lower()
            if keyword and keyword not in haystack:
                continue
            proto = pkt.get("proto", "OTHER")
            self.tree.insert(
                "", "end", iid=str(idx),
                values=(
                    pkt.get("no", "-"), pkt.get("time", "-"),
                    pkt.get("ip_src", "-"), pkt.get("ip_dst", "-"),
                    proto, pkt.get("flags", "-"), pkt.get("ttl", "-"), pkt.get("length", "-"),
                ),
                tags=(proto,),
            )

    # ------------------------------------------------------------------
    # 詳細表示（学習支援の核）
    # ------------------------------------------------------------------
    def _on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        pkt = self.packets[idx]
        self._show_detail(pkt)

    def _show_detail(self, pkt: dict):
        lines = []

        lines.append("=== Ethernet ===")
        lines.append(f"  送信元MAC : {pkt.get('eth_src', '-')}")
        lines.append(f"  宛先MAC   : {pkt.get('eth_dst', '-')}")
        lines.append("")

        lines.append("=== IP ===")
        lines.append(f"  送信元IP  : {pkt.get('ip_src', '-')}")
        lines.append(f"  宛先IP    : {pkt.get('ip_dst', '-')}")
        lines.append(f"  TTL       : {pkt.get('ttl', '-')}")
        lines.append(f"  全長      : {pkt.get('ip_len', '-')} bytes")
        lines.append("  \u2937 " + FIELD_EXPLANATIONS["ttl"].splitlines()[1])
        lines.append("")

        proto = pkt.get("proto", "-")
        lines.append(f"=== {proto} ===")
        lines.append(f"  送信元Port: {pkt.get('sport', '-')}")
        port_note = get_port_explanation(pkt.get("dport"))
        lines.append(f"  宛先Port  : {pkt.get('dport', '-')}" + (f"  ({port_note})" if port_note else ""))
        lines.append(f"  Flags     : {pkt.get('flags', '-')}")
        if "seq" in pkt:
            lines.append(f"  Seq       : {pkt.get('seq')}")
            lines.append(f"  Ack       : {pkt.get('ack')}")
        lines.append(f"  データ長  : {pkt.get('payload_len', 0)} bytes")
        lines.append("")

        flag_explains = get_flag_explanations(pkt.get("flags", ""))
        if flag_explains:
            lines.append("=== 学習メモ ===")
            for exp in flag_explains:
                lines.append(f"  \u2937 {exp}")
                lines.append("")

        # CTkTextboxはtk.Textと同じAPIで操作できる
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", "\n".join(lines))
        self.detail_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # グラフ
    # ------------------------------------------------------------------
    def _update_chart(self):
        self.ax.clear()
        if self.proto_counter:
            colors = {"TCP": "#3B8ED0", "UDP": "#2FA572", "OTHER": "#888888"}
            labels = list(self.proto_counter.keys())
            self.ax.pie(
                self.proto_counter.values(),
                labels=labels,
                autopct="%1.0f%%",
                startangle=90,
                colors=[colors.get(k, "#999999") for k in labels],
                textprops={"fontsize": 9},
            )
        self.fig.tight_layout()
        self.canvas.draw()


if __name__ == "__main__":
    app = App()
    app.mainloop()
