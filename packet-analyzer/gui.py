"""
gui.py
Tkinterによるデスクトップアプリケーション画面

役割:
  - パケット一覧のリアルタイム表示
  - パケット詳細の表示（学習支援解説つき）
  - プロトコル割合グラフの表示
  - キャプチャの開始・停止、pcap保存・読み込み
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from collections import Counter

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from analyzer import PacketAnalyzer
from explanations import FIELD_EXPLANATIONS, get_flag_explanations, get_port_explanation


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Packet Analyzer - Protocol Learning Tool")
        self.geometry("1080x680")
        self.minsize(900, 560)

        # 日本語表示のためのデフォルトフォント設定
        # WSL2 / Windows環境では明示的に指定しないと文字化けすることがある
        self._setup_fonts()

        self.analyzer = PacketAnalyzer()
        self.packets: list[dict] = []
        self.proto_counter = Counter()
        self._poll_job = None  # after()の予約IDを保持し、終了時に確実にキャンセルする

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)  # ウィンドウを閉じる際の後片付けを登録
        self._poll_queue()

    # ------------------------------------------------------------------
    # フォント設定
    # ------------------------------------------------------------------
    def _setup_fonts(self):
        """環境に応じて日本語表示可能なフォントを選び、Tk全体のデフォルトに適用する"""
        import tkinter.font as tkfont

        available = set(tkfont.families())
        # 優先順位順に候補を並べる（Windows/WSL2/Linuxいずれでも動くよう複数用意）
        candidates = [
            "Yu Gothic UI", "Yu Gothic", "Meiryo UI", "Meiryo",
            "MS Gothic", "Noto Sans CJK JP", "Takao Gothic", "IPAGothic",
        ]
        self.jp_font_family = next((f for f in candidates if f in available), None)

        if self.jp_font_family is None:
            # 候補が1つも見つからない場合はTkの既定フォントのまま進める
            self.mono_font_family = "TkFixedFont"
            return

        # ボタンやラベルなど標準ウィジェット全体のデフォルトフォントを差し替える
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family=self.jp_font_family, size=10)
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(family=self.jp_font_family, size=10)
        menu_font = tkfont.nametofont("TkMenuFont")
        menu_font.configure(family=self.jp_font_family, size=10)

        # 詳細パネル（等幅表示したいが日本語も含むため等幅フォントは使わない）
        self.mono_font_family = self.jp_font_family

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------
    def _build_ui(self):
        self._build_toolbar()

        pane = tk.PanedWindow(self, orient="horizontal", sashwidth=6)
        pane.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        left = tk.Frame(pane)
        pane.add(left, minsize=480)
        self._build_packet_table(left)

        right = tk.Frame(pane, width=340)
        pane.add(right, minsize=300)
        self._build_detail_panel(right)

    def _build_toolbar(self):
        bar = tk.Frame(self, pady=8)
        bar.pack(fill="x", padx=10)

        self.btn_start = tk.Button(bar, text="\u25b6 開始", width=10, command=self._start)
        self.btn_start.pack(side="left", padx=(0, 4))

        self.btn_stop = tk.Button(bar, text="\u25a0 停止", width=10, command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=4)

        tk.Frame(bar, width=1, bg="#ccc").pack(side="left", fill="y", padx=8)

        tk.Button(bar, text="pcap保存", width=10, command=self._save_pcap).pack(side="left", padx=4)
        tk.Button(bar, text="pcap読込", width=10, command=self._load_pcap).pack(side="left", padx=4)

        tk.Frame(bar, width=1, bg="#ccc").pack(side="left", fill="y", padx=8)

        # フィルタ
        tk.Label(bar, text="フィルタ:").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._apply_filter())
        tk.Entry(bar, textvariable=self.filter_var, width=18).pack(side="left", padx=4)

        self.proto_filter_var = tk.StringVar(value="すべて")
        proto_combo = ttk.Combobox(
            bar, textvariable=self.proto_filter_var, width=8, state="readonly",
            values=["すべて", "TCP", "UDP", "OTHER"],
        )
        proto_combo.pack(side="left", padx=4)
        proto_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_filter())

        # ステータス
        self.status_var = tk.StringVar(value="待機中")
        tk.Label(bar, textvariable=self.status_var, fg="gray").pack(side="right")

    def _build_packet_table(self, parent):
        cols = ("no", "time", "src", "dst", "proto", "flags", "ttl", "len")
        headers = {
            "no": "No", "time": "時刻", "src": "送信元IP", "dst": "宛先IP",
            "proto": "種別", "flags": "Flags", "ttl": "TTL", "len": "Len",
        }
        widths = {
            "no": 40, "time": 90, "src": 130, "dst": 130,
            "proto": 50, "flags": 90, "ttl": 40, "len": 50,
        }

        style = ttk.Style()
        style.configure("Treeview", font=(self.mono_font_family, 10), rowheight=22)
        style.configure("Treeview.Heading", font=(self.mono_font_family, 10, "bold"))

        self.tree = ttk.Treeview(parent, columns=cols, show="headings", height=24)
        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c], anchor="center" if c not in ("src", "dst") else "w")
        self.tree.pack(fill="both", expand=True, side="left")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        # プロトコルごとの行の色分け
        self.tree.tag_configure("TCP", background="#EAF2FB")
        self.tree.tag_configure("UDP", background="#E7F6EF")
        self.tree.tag_configure("OTHER", background="#F2F2F2")

    def _build_detail_panel(self, parent):
        tk.Label(parent, text="パケット詳細", font=("", 11, "bold")).pack(anchor="w", pady=(0, 4))
        self.detail_text = tk.Text(
            parent, height=16, state="disabled", wrap="word",
            font=(self.mono_font_family, 10),
        )
        self.detail_text.pack(fill="x")

        tk.Label(parent, text="プロトコル割合", font=("", 11, "bold")).pack(anchor="w", pady=(12, 4))
        self.fig, self.ax = plt.subplots(figsize=(3.2, 2.6))
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack()
        self._update_chart()

    # ------------------------------------------------------------------
    # キャプチャ制御
    # ------------------------------------------------------------------
    def _start(self):
        self.analyzer.start()
        self.status_var.set("\u25cf キャプチャ中")
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")

    def _stop(self):
        self.analyzer.stop()
        self.status_var.set("停止")
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")

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
        # 150ms間隔でキューを確認。IDを保持し、ウィンドウ終了時にキャンセルできるようにする
        self._poll_job = self.after(150, self._poll_queue)

    def _on_close(self):
        """ウィンドウを閉じる際の後片付け。予約済みのafter()を確実にキャンセルしてから終了する"""
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        self.analyzer.stop()
        self.destroy()
        # daemonスレッド(Scapyのキャプチャ)がすぐに終わらない場合があるため、
        # ウィンドウを破棄したらプロセスも明示的に終了させる
        import os
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
        self.tree.yview_moveto(1)  # 常に最新行が見えるよう自動スクロール
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

        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", "\n".join(lines))
        self.detail_text.config(state="disabled")

    # ------------------------------------------------------------------
    # グラフ
    # ------------------------------------------------------------------
    def _update_chart(self):
        self.ax.clear()
        if self.proto_counter:
            colors = {"TCP": "#378ADD", "UDP": "#1D9E75", "OTHER": "#888780"}
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