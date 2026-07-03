"""
explanations.py
学習支援機能: 各フィールドの解説文を集約したモジュール

GUI側はここから解説文を取得して表示する。
新しいフィールドの解説を増やしたいときはこの辞書に追記するだけでよい。
"""

FIELD_EXPLANATIONS = {
    "ttl": (
        "TTL (Time To Live: 生存時間)\n"
        "パケットが通過できるルーターの最大数。ルーターを1台通るたびに1減り、"
        "0になると破棄される。Windowsの初期値は128、Linuxは64が一般的。"
    ),
    "flags_syn": (
        "SYN フラグ\n"
        "「接続を開始したい」という意思表示。TCP接続の最初の一手として送られる。"
    ),
    "flags_ack": (
        "ACK フラグ\n"
        "「データを受け取った」という確認応答。接続確立後のほとんどのパケットに立つ。"
    ),
    "flags_fin": (
        "FIN フラグ\n"
        "「接続を終了したい」という意思表示。SYNで始まりFINで終わるのがTCP接続の一生。"
    ),
    "flags_rst": (
        "RST フラグ\n"
        "接続の強制リセット。エラーや不正な接続に対して即座に送られる。"
    ),
    "flags_psh": (
        "PSH フラグ\n"
        "「バッファに溜めずすぐアプリに渡してほしい」という要求。"
    ),
    "seq": (
        "シーケンス番号\n"
        "このTCPストリームで何バイト目のデータを送っているかを示す番号。"
        "接続開始時にランダムな初期値が決まり、送信データ量に応じて増加する。"
    ),
    "ack": (
        "確認応答番号 (Acknowledgment Number)\n"
        "「相手からここまでのバイト数を受け取った」ことを示す番号。"
    ),
    "sport_443": "ポート443: HTTPS（暗号化されたWeb通信）",
    "sport_80": "ポート80: HTTP（暗号化されていないWeb通信）",
    "sport_53": "ポート53: DNS（ドメイン名の名前解決）",
    "eth_src": "送信元MACアドレス: 同一ネットワーク内での送信元機器の物理アドレス",
    "eth_dst": "宛先MACアドレス: 同一ネットワーク内での宛先機器（多くの場合ルーター）の物理アドレス",
    "ip_src": "送信元IPアドレス: このパケットを送信したホストのネットワーク上の住所",
    "ip_dst": "宛先IPアドレス: このパケットの送り先ホストのネットワーク上の住所",
}


def get_flag_explanations(flags_str: str) -> list[str]:
    """'SYN,ACK' のようなフラグ文字列から該当する解説文リストを返す"""
    if not flags_str or flags_str == "-":
        return []
    explanations = []
    for flag in flags_str.split(","):
        key = f"flags_{flag.lower()}"
        if key in FIELD_EXPLANATIONS:
            explanations.append(FIELD_EXPLANATIONS[key])
    return explanations


def get_port_explanation(port) -> str | None:
    """既知のポート番号であれば解説文を返す"""
    key = f"sport_{port}"
    return FIELD_EXPLANATIONS.get(key)
