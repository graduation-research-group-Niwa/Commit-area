"""
analyzer.py
パケットキャプチャ・解析エンジン

役割:
  - Scapyでのリアルタイムパケットキャプチャ（別スレッドで実行）
  - Ethernet / IP / TCP / UDP 各層のデコード
  - キャプチャ結果を queue.Queue 経由でGUI側へ橋渡し
  - pcapファイルの保存・読み込み

このファイルはGUIに一切依存しない。単体でも動作確認できる。
"""

import threading
import queue
import time
from datetime import datetime

from scapy.all import sniff, wrpcap, rdpcap
from scapy.layers.l2 import Ether
from scapy.layers.inet import IP, TCP, UDP


class PacketAnalyzer:
    """パケットキャプチャと解析を担当するクラス"""

    def __init__(self):
        # GUIスレッドへパケットを渡すためのキュー
        self.packet_queue: "queue.Queue[dict]" = queue.Queue()

        # 内部状態
        self.running = False
        self._thread: threading.Thread | None = None

        # 保存用（pcap出力・再解析用に生パケットも保持する）
        self.raw_packets = []

    # ------------------------------------------------------------------
    # キャプチャの開始・停止
    # ------------------------------------------------------------------
    def start(self, iface: str | None = None):
        """キャプチャを別スレッドで開始する"""
        if self.running:
            return  # 二重起動防止
        self.running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            args=(iface,),
            daemon=True,  # メインウィンドウを閉じたら自動終了させる
        )
        self._thread.start()

    def stop(self):
        """キャプチャを停止する"""
        self.running = False

    # ------------------------------------------------------------------
    # 内部処理
    # ------------------------------------------------------------------
    def _capture_loop(self, iface):
        """Scapyのsniff()をブロッキングで回すスレッド本体"""
        try:
            sniff(
                iface=iface,
                prn=self._on_packet,      # パケット到着ごとに呼ばれるコールバック
                store=False,               # Scapy内部にはためない（自前でraw_packetsに保持）
                stop_filter=lambda _: not self.running,
            )
        except PermissionError:
            self.packet_queue.put({
                "error": "権限エラー: 管理者権限(sudo)で実行してください"
            })
        except Exception as e:  # noqa: BLE001
            self.packet_queue.put({"error": f"キャプチャエラー: {e}"})

    def _on_packet(self, pkt):
        self.raw_packets.append(pkt)
        parsed = self._parse(pkt)
        if parsed:
            self.packet_queue.put(parsed)

    def _parse(self, pkt) -> dict | None:
        """パケットをEthernet/IP/TCP/UDPの各層に分解して辞書化する"""
        result = {
            "no": len(self.raw_packets),
            "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "length": len(pkt),
        }

        if Ether in pkt:
            result["eth_src"] = pkt[Ether].src
            result["eth_dst"] = pkt[Ether].dst

        if IP in pkt:
            result["ip_src"] = pkt[IP].src
            result["ip_dst"] = pkt[IP].dst
            result["ttl"] = pkt[IP].ttl
            result["ip_len"] = pkt[IP].len
        else:
            # IP層がないパケット（ARPなど）は今回のスコープ外として除外
            return None

        if TCP in pkt:
            result["proto"] = "TCP"
            result["sport"] = pkt[TCP].sport
            result["dport"] = pkt[TCP].dport
            result["flags"] = self._decode_tcp_flags(pkt[TCP].flags)
            result["seq"] = pkt[TCP].seq
            result["ack"] = pkt[TCP].ack
            result["payload_len"] = len(pkt[TCP].payload)
        elif UDP in pkt:
            result["proto"] = "UDP"
            result["sport"] = pkt[UDP].sport
            result["dport"] = pkt[UDP].dport
            result["flags"] = "-"
            result["payload_len"] = len(pkt[UDP].payload)
        else:
            result["proto"] = "OTHER"
            result["sport"] = "-"
            result["dport"] = "-"
            result["flags"] = "-"
            result["payload_len"] = 0

        return result

    @staticmethod
    def _decode_tcp_flags(flags) -> str:
        """ScapyのFlagValueを人間が読みやすい文字列に変換する"""
        flag_map = {
            "F": "FIN", "S": "SYN", "R": "RST",
            "P": "PSH", "A": "ACK", "U": "URG",
        }
        names = [flag_map[c] for c in str(flags) if c in flag_map]
        return ",".join(names) if names else "-"

    # ------------------------------------------------------------------
    # pcap 保存・読み込み（Wireshark互換）
    # ------------------------------------------------------------------
    def save_pcap(self, filepath: str) -> int:
        """キャプチャ済みパケットをpcapファイルに保存する。保存件数を返す"""
        if not self.raw_packets:
            return 0
        wrpcap(filepath, self.raw_packets)
        return len(self.raw_packets)

    def load_pcap(self, filepath: str) -> list[dict]:
        """pcapファイルを読み込み、解析済み辞書のリストを返す"""
        packets = rdpcap(filepath)
        self.raw_packets = list(packets)
        parsed_list = []
        for i, pkt in enumerate(packets, start=1):
            parsed = self._parse_for_load(pkt, i)
            if parsed:
                parsed_list.append(parsed)
        return parsed_list

    def _parse_for_load(self, pkt, no: int) -> dict | None:
        """pcap読み込み時用。連番を外部から指定できるようにした_parseの派生"""
        original_len = len(self.raw_packets)
        self.raw_packets_backup_len = original_len
        result = self._parse(pkt)
        if result:
            result["no"] = no
            result["time"] = "-"  # 過去ログのため時刻はpcap保存時点のものを使わない簡易対応
        return result


# ----------------------------------------------------------------------
# 単体動作確認用（GUIなしでこのファイルだけ実行して確認できる）
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("パケットキャプチャを開始します（5秒間・要sudo）")
    analyzer = PacketAnalyzer()
    analyzer.start()

    time.sleep(5)
    analyzer.stop()

    print(f"\n取得パケット数: {len(analyzer.raw_packets)}")
    while not analyzer.packet_queue.empty():
        pkt = analyzer.packet_queue.get()
        if "error" in pkt:
            print("ERROR:", pkt["error"])
            continue
        print(
            f"[{pkt['no']:>3}] {pkt['time']} "
            f"{pkt['ip_src']:>15} -> {pkt['ip_dst']:<15} "
            f"{pkt['proto']:<4} flags={pkt['flags']:<10} ttl={pkt['ttl']}"
        )
