"""Phase 3 analysis diagrams → doc/sdlc/diagrams/*.drawio + *.png.
Run from the repo root: python doc/sdlc/build/analysis_diagrams.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from drawio_lib import Diagram  # noqa: E402

OUT = Path(__file__).parents[1] / "diagrams"
GREY, RED, GREEN = "#5B6B7B", "#C0504D", "#548235"


def save(d, name):
    d.write_drawio(OUT / f"{name}.drawio")
    print(name, "\n".join(d.render_png(OUT / f"{name}.png")) or "ok")


def decomposition():
    d = Diagram(1460, 470, "functional decomposition")
    d.box("root", 630, 20, 200, 50, ["VTAgent"], "blue", size=15)
    modules = [
        ("1. Quản lý tài liệu", ["Nạp tài liệu", "Xem danh sách", "Xóa tài liệu", "Cập nhật phiên bản"]),
        ("2. Xử lý tài liệu", ["Kiểm tra tệp", "Trích văn bản", "Nhận diện cấu trúc", "Chia đoạn, lập chỉ mục"]),
        ("3. Hỏi đáp", ["Hiểu câu hỏi", "Tìm bằng chứng", "Soạn câu trả lời", "Từ chối khi thiếu căn cứ"]),
        ("4. Trích dẫn, kiểm chứng", ["Gắn trích dẫn", "Xem đoạn gốc", "Kiểm chứng câu trả lời", "Đánh dấu thiếu căn cứ"]),
        ("5. Phân tích", ["So sánh nhiều tài liệu", "Câu hỏi về cấu trúc", "Tính toán số liệu", "Rà soát theo quy tắc"]),
        ("6. Hội thoại", ["Lưu lịch sử", "Hỏi tiếp theo ngữ cảnh", "Xóa hội thoại"]),
        ("7. Quản trị", ["Cấu hình quy tắc", "Xuất báo cáo"]),
    ]
    for i, (name, leaves) in enumerate(modules):
        mx = 20 + i * 205
        d.box(f"m{i}", mx, 120, 185, 56, [name], "yellow", size=13)
        d.edge("root", f"m{i}", [(730, 70), (730, 95), (mx + 92, 95), (mx + 92, 120)], arrow=False)
        for k, leaf in enumerate(leaves):
            ly = 200 + k * 62
            d.box(f"l{i}{k}", mx + 28, ly, 157, 48, [leaf], size=12)
            d.edge(f"m{i}", f"l{i}{k}", [(mx + 14, 176), (mx + 14, ly + 24), (mx + 28, ly + 24)], arrow=False)
    save(d, "p3_functional_decomposition")


def use_cases():
    d = Diagram(1320, 950, "use case")
    d.box("sys", 270, 30, 780, 740, ["Hệ thống VTAgent"], "panel", shape="panel", size=14)
    d.box("user", 40, 330, 150, 70, ["Người dùng cuối", "tác nhân chính"], "store", shape="swatch")
    d.box("admin", 1110, 260, 180, 70, ["Quản trị tài liệu", "tác nhân chính"], "store", shape="swatch")
    d.box("model", 600, 850, 230, 70, ["Dịch vụ mô hình cục bộ", "tác nhân phụ"], "store", shape="swatch")
    col1 = [("uc05", "UC05", "Đặt câu hỏi"), ("uc09", "UC09", "Xem trích dẫn, đoạn gốc"),
            ("uc10", "UC10", "So sánh, tổng hợp"), ("uc11", "UC11", "Rà soát theo quy tắc"),
            ("uc12", "UC12", "Quản lý hội thoại"), ("uc14", "UC14", "Xuất báo cáo")]
    col2 = [("uc06", "UC06", "Truy xuất bằng chứng"), ("uc07", "UC07", "Soạn câu trả lời"),
            ("uc08", "UC08", "Kiểm chứng câu trả lời")]
    col3 = [("uc01", "UC01", "Nạp tài liệu"), ("uc02", "UC02", "Xem danh sách tài liệu"),
            ("uc03", "UC03", "Xóa tài liệu"), ("uc04", "UC04", "Cập nhật tài liệu"),
            ("uc13", "UC13", "Cấu hình quy tắc")]
    for x, w, col in [(300, 220, col1), (580, 220, col2), (830, 200, col3)]:
        for k, (cid, code, name) in enumerate(col):
            d.box(cid, x, 90 + k * 110, w, 64, [code, name], parent="sys", shape="ellipse", size=12)
    for k, (cid, _, _) in enumerate(col1):
        d.edge("user", cid, [(190, 365), (300, 122 + k * 110)], arrow=False)
    for k, (cid, _, _) in enumerate(col3):
        d.edge("admin", cid, [(1110, 295), (1030, 122 + k * 110)], arrow=False)
    for k, (cid, _, _) in enumerate(col2):
        d.edge("uc05", cid, [(520, 122), (580, 122 + k * 110)], dashed=True)
    d.text(523, 150, 56, 30, "«include»", GREY, 10)
    d.edge("uc09", "uc05", [(410, 200), (410, 154)], dashed=True)
    d.text(416, 166, 70, 20, "«extend»", GREY, 10, "left")
    d.edge("uc07", "model", [(800, 232), (815, 232), (815, 850)], arrow=False)
    d.edge("uc08", "model", [(690, 374), (690, 850)], arrow=False)
    save(d, "p3_use_case")


def ingest_flow():
    d = Diagram(900, 1060, "ingest flow")
    d.box("start", 260, 20, 80, 50, ["Bắt đầu"], "dark", shape="ellipse", size=12, font_color="#FFFFFF")
    steps = [("n1", 100, 50, "rounded", ["Người dùng chọn tệp"]),
             ("d1", 180, 90, "diamond", ["Định dạng", "được hỗ trợ?"]),
             ("d2", 310, 90, "diamond", ["Đã có", "trong kho?"]),
             ("n2", 440, 50, "rounded", ["Trích văn bản"]),
             ("d3", 520, 90, "diamond", ["Có lớp", "văn bản?"]),
             ("n3", 650, 50, "rounded", ["Nhận diện thể loại, cấu trúc"]),
             ("n4", 730, 50, "rounded", ["Chia đoạn theo cấu trúc"]),
             ("n5", 810, 56, "rounded", ["Lập chỉ mục, lưu tệp gốc", "và danh mục tài liệu"]),
             ("n6", 896, 50, "green", ["Báo nạp thành công"])]
    prev, prev_bottom = "start", 70
    for cid, y, h, shape, lines in steps:
        color = "yellow" if shape == "diamond" else ("green" if shape == "green" else "node")
        d.box(cid, 180, y, 240, h, lines, color, shape="diamond" if shape == "diamond" else "rounded", size=12)
        d.edge(prev, cid, [(300, prev_bottom), (300, y)])
        prev, prev_bottom = cid, y + h
    d.box("end", 260, 980, 80, 50, ["Kết thúc"], "dark", shape="ellipse", size=12, font_color="#FFFFFF")
    d.edge("n6", "end", [(300, 946), (300, 980)])
    for lbl, y in [("Có", 270), ("Chưa", 400), ("Có", 610)]:
        d.text(306, y + 6, 50, 18, lbl, GREEN, 11, "left")
    rejects = [("r1", "d1", 225, ["Từ chối: định dạng", "không hỗ trợ"], "Không"),
               ("r2", "d2", 355, ["Báo đã tồn tại,", "không nạp lại"], "Có"),
               ("r3", "d3", 565, ["Từ chối: tài liệu", "dạng ảnh quét"], "Không")]
    d.box("endx", 680, 980, 90, 50, ["Kết thúc"], "dark", shape="ellipse", size=12, font_color="#FFFFFF")
    for rid, did, cy, lines, lbl in rejects:
        d.box(rid, 560, cy - 28, 240, 56, lines, "red", size=12)
        d.edge(did, rid, [(420, cy), (560, cy)], RED)
        d.text(430, cy - 22, 80, 18, lbl, RED, 11, "left")
        d.edge(rid, "endx", [(800, cy), (845, cy), (845, 1005), (770, 1005)], RED)
    save(d, "p3_flow_ingest")


def query_flow():
    d = Diagram(920, 1100, "query flow")
    d.box("start", 380, 20, 80, 50, ["Bắt đầu"], "dark", shape="ellipse", size=12, font_color="#FFFFFF")
    d.box("q1", 300, 100, 240, 50, ["Người dùng nhập câu hỏi"], size=12)
    d.box("q2", 300, 180, 240, 56, ["Hiểu câu hỏi: loại câu hỏi,", "tài liệu liên quan"], size=12)
    d.box("dq", 300, 266, 240, 90, ["Loại câu hỏi?"], "yellow", shape="diamond", size=12)
    d.box("q3", 300, 396, 240, 50, ["Tìm bằng chứng"], size=12)
    d.box("dq2", 300, 476, 240, 90, ["Có bằng chứng", "liên quan?"], "yellow", shape="diamond", size=12)
    d.box("q4", 300, 606, 240, 50, ["Soạn câu trả lời có trích dẫn"], size=12)
    d.box("a1", 640, 396, 240, 50, ["Lập kế hoạch phân tích"], size=12)
    d.box("a2", 640, 476, 240, 50, ["Lấy bằng chứng từng tài liệu"], size=12)
    d.box("a3", 640, 556, 240, 50, ["Tính toán, đối chiếu, rà soát"], size=12)
    d.box("a4", 640, 636, 240, 50, ["Soạn kết quả có trích dẫn"], size=12)
    d.box("v1", 300, 716, 240, 50, ["Kiểm chứng câu trả lời"], "blue", size=12)
    d.box("dv", 300, 806, 240, 90, ["Đạt?"], "yellow", shape="diamond", size=12)
    d.box("out", 300, 936, 240, 50, ["Trả câu trả lời và trích dẫn"], "green", size=12)
    d.box("end", 380, 1016, 80, 50, ["Kết thúc"], "dark", shape="ellipse", size=12, font_color="#FFFFFF")
    d.box("nf", 40, 496, 200, 50, ["Trả lời: không tìm thấy"], "red", size=12)
    d.box("dr", 40, 806, 220, 90, ["Còn lượt", "kiểm chứng?"], "yellow", shape="diamond", size=12)
    d.box("retry", 40, 676, 220, 56, ["Tìm thêm bằng chứng,", "soạn lại"], size=12)
    d.box("warn", 40, 936, 220, 50, ["Trả lời kèm cảnh báo"], "yellow", size=12)
    for a, b, y0, y1 in [("start", "q1", 70, 100), ("q1", "q2", 150, 180), ("q2", "dq", 236, 266),
                         ("dq", "q3", 356, 396), ("q3", "dq2", 446, 476), ("dq2", "q4", 566, 606),
                         ("q4", "v1", 656, 716), ("v1", "dv", 766, 806), ("dv", "out", 896, 936), ("out", "end", 986, 1016)]:
        d.edge(a, b, [(420, y0), (420, y1)])
    for a, b, y0, y1 in [("a1", "a2", 446, 476), ("a2", "a3", 526, 556), ("a3", "a4", 606, 636)]:
        d.edge(a, b, [(760, y0), (760, y1)])
    d.edge("dq", "a1", [(540, 311), (760, 311), (760, 396)])
    d.text(560, 290, 90, 18, "Phân tích", GREY, 11, "left")
    d.text(426, 364, 70, 18, "Tra cứu", GREY, 11, "left")
    d.edge("a4", "v1", [(760, 686), (760, 741), (540, 741)])
    d.edge("dq2", "nf", [(300, 521), (240, 521)], RED)
    d.text(246, 500, 50, 18, "Không", RED, 11, "left")
    d.text(426, 572, 30, 18, "Có", GREEN, 11, "left")
    d.edge("dv", "dr", [(300, 851), (260, 851)], RED)
    d.text(262, 828, 40, 18, "Không", RED, 11, "left")
    d.text(426, 902, 30, 18, "Có", GREEN, 11, "left")
    d.edge("dr", "retry", [(150, 806), (150, 732)])
    d.text(156, 760, 30, 18, "Có", GREEN, 11, "left")
    d.edge("retry", "q4", [(260, 704), (280, 704), (280, 631), (300, 631)])
    d.edge("dr", "warn", [(150, 896), (150, 936)], RED)
    d.text(156, 904, 50, 18, "Không", RED, 11, "left")
    d.edge("warn", "end", [(150, 986), (150, 1041), (380, 1041)])
    d.edge("nf", "end", [(40, 521), (20, 521), (20, 1041), (380, 1041)])
    save(d, "p3_flow_query")


def dfd0():
    d = Diagram(1100, 470, "DFD level 0")
    d.box("p0", 430, 180, 240, 200, ["0", "VTAgent"], "blue", shape="ellipse", size=16)
    d.box("user", 40, 240, 200, 80, ["Người dùng cuối"], "store", shape="rect")
    d.box("admin", 440, 20, 220, 70, ["Quản trị tài liệu"], "store", shape="rect")
    d.box("model", 860, 240, 200, 80, ["Dịch vụ mô hình", "cục bộ"], "store", shape="rect")
    d.edge("user", "p0", [(240, 262), (432, 262)])
    d.text(250, 238, 180, 20, "câu hỏi", size=11)
    d.edge("p0", "user", [(432, 298), (240, 298)])
    d.text(240, 302, 200, 34, "câu trả lời, trích dẫn,\ncảnh báo, kết quả rà soát", size=11)
    d.edge("admin", "p0", [(520, 90), (520, 183)])
    d.text(330, 112, 185, 50, "tệp tài liệu, quy tắc,\nlệnh xóa, cập nhật", size=11, align="right")
    d.edge("p0", "admin", [(580, 183), (580, 90)])
    d.text(588, 112, 200, 50, "kết quả nạp,\ndanh sách tài liệu", size=11, align="left")
    d.edge("p0", "model", [(668, 262), (860, 262)])
    d.text(672, 230, 186, 30, "yêu cầu sinh:\ncâu hỏi, bằng chứng", size=11)
    d.edge("model", "p0", [(860, 298), (668, 298)])
    d.text(672, 302, 186, 20, "văn bản sinh", size=11)
    save(d, "p3_dfd_level0")


def dfd1():
    d = Diagram(1400, 800, "DFD level 1")
    d.box("admin", 20, 80, 180, 70, ["Quản trị tài liệu"], "store", shape="rect")
    d.box("user", 20, 620, 180, 70, ["Người dùng cuối"], "store", shape="rect")
    d.box("model", 700, 430, 200, 60, ["Dịch vụ mô hình cục bộ"], "store", shape="rect", size=12)
    procs = [("p1", 280, 70, ["1.0", "Tiếp nhận, kiểm tra tệp"]), ("p2", 560, 70, ["2.0", "Phân tích cấu trúc"]),
             ("p3", 840, 70, ["3.0", "Chia đoạn, lập chỉ mục"]), ("p7", 1120, 70, ["7.0", "Quản lý tài liệu, quy tắc"]),
             ("p4", 420, 610, ["4.0", "Hiểu câu hỏi, truy xuất"]), ("p5", 700, 610, ["5.0", "Soạn trả lời, phân tích"]),
             ("p6", 980, 610, ["6.0", "Kiểm chứng, trích dẫn"])]
    for cid, x, y, lines in procs:
        d.box(cid, x, y, 200, 90, lines, "blue", shape="ellipse", size=12)
    for cid, x, y, w, name in [("d1", 280, 330, 200, "D1 Kho tệp gốc"), ("d3", 560, 330, 200, "D3 Danh mục tài liệu"),
                               ("d2", 840, 330, 200, "D2 Chỉ mục đoạn"), ("d5", 1100, 330, 220, "D5 Bộ quy tắc rà soát"),
                               ("d4", 220, 470, 180, "D4 Lịch sử hội thoại"), ("d6", 1180, 450, 200, "D6 Kết quả rà soát")]:
        d.box(cid, x, y, w, 46, [name], "data", shape="rect", size=12)
    flows = [("admin", "p1", [(200, 115), (280, 115)], "tệp", (205, 92, 70, 18)),
             ("p1", "p2", [(480, 115), (560, 115)], "tệp hợp lệ", (482, 92, 76, 18)),
             ("p2", "p3", [(760, 115), (840, 115)], "văn bản có\ncấu trúc", (762, 80, 76, 32)),
             ("p3", "d2", [(940, 160), (940, 330)], "đoạn, chỉ mục", (946, 236, 100, 18)),
             ("admin", "p7", [(110, 80), (110, 30), (1220, 30), (1220, 70)], "lệnh xóa, cập nhật, quy tắc", (560, 10, 260, 18)),
             ("p7", "d5", [(1220, 160), (1220, 330)], "quy tắc", (1226, 236, 70, 18)),
             ("user", "p4", [(200, 655), (420, 655)], "câu hỏi", (230, 632, 80, 18)),
             ("d3", "p4", [(580, 376), (580, 610)], "", None),
             ("d2", "p4", [(900, 376), (900, 410), (600, 410), (600, 610)], "đoạn liên quan", (606, 556, 100, 18)),
             ("p4", "p5", [(620, 655), (700, 655)], "", None),
             ("p5", "model", [(780, 610), (780, 490)], "yêu cầu sinh", (690, 526, 86, 18)),
             ("model", "p5", [(820, 490), (820, 610)], "văn bản sinh", (826, 526, 90, 18)),
             ("d5", "p5", [(1160, 376), (1160, 560), (860, 560), (860, 610)], "quy tắc rà soát", (1000, 540, 110, 18)),
             ("p5", "p6", [(900, 655), (980, 655)], "", None),
             ("p5", "d6", [(880, 628), (880, 585), (1280, 585), (1280, 496)], "phát hiện", (1190, 566, 80, 18)),
             ("d6", "p6", [(1340, 496), (1340, 655), (1180, 655)], "kết quả rà soát", (1192, 660, 140, 18)),
             ("p6", "user", [(1080, 700), (1080, 770), (110, 770), (110, 690)], "câu trả lời, trích dẫn, cảnh báo, kết quả rà soát", (420, 774, 330, 18))]
    for a, b, pts, label, box in flows:
        d.edge(a, b, pts)
        if box:
            d.text(*box, label, size=10, align="left")
    d.edge("p1", "d1", [(380, 160), (380, 330)], both=True)
    d.text(386, 226, 90, 32, "tệp gốc,\nmã băm", size=10, align="left")
    d.edge("p2", "d3", [(660, 160), (660, 330)], both=True)
    d.text(666, 226, 90, 32, "thể loại,\nsiêu dữ liệu", size=10, align="left")
    d.edge("d4", "p4", [(400, 493), (440, 493), (440, 615)], both=True)
    d.text(330, 520, 100, 18, "lịch sử", size=10, align="left")
    d.edge("p6", "d4", [(1020, 691), (1020, 740), (310, 740), (310, 516)])
    d.text(316, 700, 120, 32, "câu trả lời,\ntrích dẫn", size=10, align="left")
    # D1 drawn a second time next to 6.0 to avoid a long crossing line.
    d.box("d1b", 1200, 730, 180, 40, ["D1 Kho tệp gốc"], "data", shape="rect", size=12)
    d.edge("d1b", "p6", [(1200, 750), (1150, 750), (1150, 689)])
    d.text(1158, 700, 90, 18, "đoạn gốc", size=10, align="left")
    d.text(1232, 172, 166, 48, "khi xóa tài liệu: xóa\ndữ liệu liên quan ở\nD1, D2, D3, D4, D6", GREY, 10, "left")
    save(d, "p3_dfd_level1")


def erd():
    """Conceptual ERD: entities and cardinalities only; attributes are listed in the SRS tables."""
    d = Diagram(1300, 780, "conceptual ERD")
    ents = [("ten", 40, 40, "Tenant", "D3", "node"), ("cat", 380, 40, "Thể loại", "D3", "blue"), ("rule", 1060, 40, "Quy tắc rà soát", "D5", "yellow"),
            ("conv", 40, 200, "Hội thoại", "D4", "green"), ("doc", 380, 200, "Tài liệu", "D3", "blue"),
            ("rel", 720, 200, "Quan hệ văn bản", "D3", "blue"),
            ("turn", 40, 360, "Lượt hỏi đáp", "D4", "green"), ("ver", 380, 360, "Phiên bản", "D3", "blue"),
            ("run", 720, 360, "Lần rà soát", "D6", "yellow"), ("find", 1060, 360, "Phát hiện", "D6", "yellow"),
            ("cite", 40, 520, "Trích dẫn", "D4", "green"), ("node", 380, 520, "Nút cấu trúc", "D2", "blue"),
            ("file", 720, 520, "Tệp gốc", "D1", "blue"), ("chunk", 380, 680, "Đoạn", "D2", "blue")]
    for cid, x, y, name, store, color in ents:
        d.box(cid, x, y, 200, 60, [name, f"kho {store}"], color, shape="rect", size=13)
    # (src, dst, polyline, verb label box, (card at src), (card at dst))
    rels = [("cat", "doc", [(480, 100), (480, 200)], ("phân loại", 488, 140), ("1", 486, 102), ("n", 486, 180)),
            ("cat", "rule", [(580, 70), (1060, 70)], ("áp dụng cho", 770, 50), ("1", 586, 50), ("n", 1040, 50)),
            ("conv", "turn", [(140, 260), (140, 360)], ("gồm", 148, 300), ("1", 146, 262), ("n", 146, 340)),
            ("doc", "ver", [(480, 260), (480, 360)], ("có", 488, 300), ("1", 486, 262), ("n", 486, 340)),
            ("doc", "rel", [(580, 215), (720, 215)], ("là nguồn", 618, 196), ("1", 586, 196), ("n", 704, 196)),
            ("doc", "rel", [(580, 245), (720, 245)], ("là đích", 622, 248), ("1", 586, 248), ("n", 704, 248)),
            ("turn", "doc", [(240, 375), (310, 375), (310, 230), (380, 230)], ("phạm vi hỏi", 228, 290),
             ("n", 246, 356), ("n", 362, 232)),
            ("ten", "conv", [(140, 100), (140, 200)], ("sở hữu", 148, 140), ("1", 146, 102), ("n", 146, 180)),
            ("ten", "doc", [(240, 85), (340, 85), (340, 212), (380, 212)], ("sở hữu", 266, 66), ("1", 246, 66),
             ("n", 362, 192)),
            ("ten", "rule", [(140, 40), (140, 16), (1160, 16), (1160, 40)], ("sở hữu", 770, 0), ("1", 146, 20),
             ("n", 1166, 20)),
            ("turn", "cite", [(140, 420), (140, 520)], ("có", 148, 460), ("1", 146, 422), ("n", 146, 500)),
            ("chunk", "cite", [(380, 710), (140, 710), (140, 580)], ("được trích", 220, 690), ("1", 362, 690),
             ("n", 146, 584)),
            ("ver", "node", [(480, 420), (480, 520)], ("gồm", 488, 460), ("1", 486, 422), ("n", 486, 500)),
            ("node", "node", [(380, 535), (330, 535), (330, 565), (380, 565)], ("cha – con", 256, 541),
             ("1", 362, 516), ("n", 362, 566)),
            ("node", "chunk", [(480, 580), (480, 680)], ("chứa", 488, 620), ("1", 486, 582), ("n", 486, 660)),
            ("ver", "run", [(580, 375), (720, 375)], ("được rà soát", 604, 356), ("1", 586, 377), ("n", 704, 377)),
            ("ver", "file", [(580, 405), (650, 405), (650, 550), (720, 550)], ("lưu ở", 658, 470),
             ("1", 586, 407), ("1", 704, 530)),
            ("run", "find", [(920, 390), (1060, 390)], ("tạo ra", 966, 370), ("1", 926, 392), ("n", 1044, 392)),
            ("rule", "find", [(1160, 100), (1160, 360)], ("sinh ra", 1168, 220), ("1", 1166, 102), ("n", 1166, 340)),
            ("find", "chunk", [(1160, 420), (1160, 725), (580, 725)], ("dẫn chứng", 1050, 705), ("n", 1166, 424),
             ("n", 586, 727))]
    for src, dst, pts, (verb, vx, vy), (c1, x1, y1), (c2, x2, y2) in rels:
        d.edge(src, dst, pts, arrow=False)
        d.text(vx, vy, 90, 18, verb, GREY, 11, "left")
        d.text(x1, y1, 14, 18, c1, "#C0504D", 12, "left", bold=True)
        d.text(x2, y2, 14, 18, c2, "#C0504D", 12, "left", bold=True)
    save(d, "p3_erd_conceptual")


def erd_tenancy():
    """Authorization entities for the multi-tenant extension; dashed = not in this version."""
    d = Diagram(1300, 460, "tenancy ERD")
    ents = [("user", 40, 40, "Người dùng", "node", True), ("mem", 380, 40, "Thành viên", "node", True),
            ("ten", 720, 40, "Tenant", "node", False),
            ("gmem", 40, 200, "Thành viên nhóm", "node", True), ("grp", 380, 200, "Nhóm", "node", True),
            ("log", 1060, 200, "Nhật ký truy cập", "node", True),
            ("conv", 40, 360, "Hội thoại", "green", False), ("perm", 380, 360, "Quyền không gian", "node", True),
            ("space", 720, 360, "Không gian tài liệu", "node", True), ("doc", 1060, 360, "Tài liệu", "blue", False)]
    for cid, x, y, name, color, planned in ents:
        d.box(cid, x, y, 200, 60, [name], color, planned=planned, shape="rect", size=13)
    rels = [("user", "mem", [(240, 70), (380, 70)], ("có", 300, 50), ("1", 246, 50), ("n", 364, 50)),
            ("ten", "mem", [(720, 70), (580, 70)], ("gồm", 636, 50), ("1", 704, 50), ("n", 586, 50)),
            ("user", "gmem", [(140, 100), (140, 200)], ("thuộc", 148, 140), ("1", 146, 102), ("n", 146, 180)),
            ("grp", "gmem", [(380, 230), (240, 230)], ("gồm", 296, 210), ("1", 364, 210), ("n", 246, 210)),
            ("ten", "grp", [(760, 100), (760, 150), (480, 150), (480, 200)], ("có", 600, 130), ("1", 766, 102),
             ("n", 486, 180)),
            ("grp", "perm", [(480, 260), (480, 360)], ("được cấp", 488, 300), ("1", 486, 262), ("n", 486, 340)),
            ("space", "perm", [(720, 390), (580, 390)], ("cấp cho", 620, 370), ("1", 704, 370), ("n", 586, 370)),
            ("ten", "space", [(860, 100), (860, 360)], ("có", 868, 220), ("1", 866, 102), ("n", 866, 340)),
            ("space", "doc", [(920, 390), (1060, 390)], ("chứa", 970, 370), ("1", 926, 370), ("n", 1044, 370)),
            ("user", "conv", [(40, 70), (20, 70), (20, 390), (40, 390)], ("sở hữu", 26, 290), ("1", 24, 50),
             ("n", 24, 396)),
            ("user", "log", [(140, 40), (140, 16), (1160, 16), (1160, 200)], ("thực hiện", 640, 0),
             ("1", 146, 20), ("n", 1166, 180))]
    for src, dst, pts, (verb, vx, vy), (c1, x1, y1), (c2, x2, y2) in rels:
        d.edge(src, dst, pts, arrow=False)
        d.text(vx, vy, 90, 18, verb, GREY, 11, "left")
        d.text(x1, y1, 14, 18, c1, "#C0504D", 12, "left", bold=True)
        d.text(x2, y2, 14, 18, c2, "#C0504D", 12, "left", bold=True)
    save(d, "p3_erd_tenancy")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    decomposition()
    use_cases()
    ingest_flow()
    query_flow()
    dfd0()
    dfd1()
    erd()
    erd_tenancy()
