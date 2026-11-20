"""Phase 4 design diagrams → doc/sdlc/diagrams/p4_*.drawio + *.png.
Run from the repo root: python doc/sdlc/build/design_diagrams.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from drawio_lib import Diagram  # noqa: E402

OUT = Path(__file__).parents[1] / "diagrams"
GREY, RED, GREEN, BLUE = "#5B6B7B", "#C0504D", "#548235", "#2C5F8A"


def save(d, name):
    d.write_drawio(OUT / f"{name}.drawio")
    print(name, "\n".join(d.render_png(OUT / f"{name}.png")) or "ok")


def row(d, prefix, parent, x0, y, width, h, items, color="node", size=12):
    """Lay ``items`` (each a list of lines) out evenly in one row inside ``parent``."""
    gap = 12
    w = (width - gap * (len(items) - 1)) / len(items)
    for i, lines in enumerate(items):
        d.box(f"{prefix}{i}", x0 + i * (w + gap), y, w, h, lines, color, parent=parent, size=size)


def layers():
    d = Diagram(1320, 850, "layered architecture")
    spec = [
        ("L1", 20, 100, "Tầng trình bày: giao diện web (React, chạy trong trình duyệt)",
         [["Hỏi đáp, trích dẫn"], ["Quản lý tài liệu"], ["Rà soát, báo cáo"], ["Bộ quy tắc"], ["Hệ thống"]]),
        ("L2", 150, 100, "Tầng API: FastAPI, chỉ lắng nghe 127.0.0.1 (api/)",
         [["/documents", "/jobs"], ["/conversations", "/turns"], ["/reviews", "/rules"], ["Sự kiện SSE"],
          ["Ngữ cảnh yêu cầu", "tenant mặc định"], ["Hàng đợi tác vụ", "1 worker"]]),
        ("L3", 280, 100, "Tầng điều phối: LangGraph (agents/)",
         [["Coordinator"], ["RAG Agent"], ["Analyst Agent"], ["Validator Agent"], ["Luồng nạp"]]),
        ("L4", 410, 150, "Tầng nghiệp vụ: thư viện core/, không biết tới tác tử",
         [["parsing", "đọc PDF, DOCX"], ["structure", "thể loại, cấu trúc"], ["chunking"], ["indexing", "dense, BM25"],
          ["retrieval", "hybrid, RRF"]],
         [["rerank"], ["context", "lắp ngữ cảnh"], ["llm", "gọi mô hình"], ["tools", "tính, dàn ý, quy tắc"],
          ["checks", "kiểm tra số liệu"]]),
        ("L5", 590, 100, "Tầng truy cập dữ liệu: repository (core/stores)",
         [["DocumentRepo"], ["ChunkIndex"], ["ConversationRepo"], ["RuleRepo", "ReviewRepo"], ["JobRepo"],
          ["FileStore"]]),
        ("L6", 720, 100, "Kho dữ liệu",
         [["SQLite: data/vtagent.db", "D3, D4, D5, D6"], ["Qdrant: vtagent_chunks_*", "D2"],
          ["Thư mục data/files", "D1"]]),
    ]
    for item in spec:
        cid, y, h, title, *rows = item
        d.box(cid, 20, y, 990, h, [title], "panel", shape="panel", size=13)
        if len(rows) == 1:
            row(d, f"{cid}b", cid, 40, y + 38, 950, h - 52, rows[0])
        else:
            row(d, f"{cid}a", cid, 40, y + 36, 950, 48, rows[0], size=11)
            row(d, f"{cid}b", cid, 40, y + 92, 950, 48, rows[1], size=11)
    for a, b, y0, y1 in [("L1", "L2", 120, 150), ("L2", "L3", 250, 280), ("L3", "L4", 380, 410),
                         ("L4", "L5", 560, 590), ("L5", "L6", 690, 720)]:
        d.edge(a, b, [(515, y0), (515, y1)])
    d.text(522, 122, 160, 26, "HTTP, JSON, SSE", GREY, 10, "left")
    d.box("ai", 1050, 280, 250, 280, ["Hạ tầng AI (cục bộ)"], "panel", shape="panel", size=13)
    d.box("oll", 1066, 318, 218, 130, ["Ollama 127.0.0.1:11434", "qwen3.5:9b: soạn, diễn giải", "qwen3.5:4b: định tuyến,",
                                       "lập kế hoạch, kiểm chứng", "bge-m3: vector 1024 chiều"], "blue", parent="ai", size=12)
    d.box("onnx", 1066, 462, 218, 80, ["ONNX Runtime (CPU)", "bge-reranker-v2-m3 int8"], "blue", parent="ai", size=12)
    d.edge("L3", "ai", [(1010, 330), (1050, 330)])
    d.edge("L4", "ai", [(1010, 500), (1050, 500)])
    d.box("cfg", 1050, 620, 250, 200, ["Lắp ráp và cấu hình", "config.py: Settings,", "biến VTAGENT_*, tệp .env",
                                       "agent_factory.py: nơi duy nhất", "đọc cấu hình, dựng các khối"], "yellow", size=12)
    d.edge("cfg", "L5", [(1050, 640), (1010, 640)], dashed=True)
    save(d, "p4_layered_architecture")


def agents():
    d = Diagram(1400, 760, "multi-agent query graph")
    d.box("start", 30, 350, 80, 44, ["START"], "dark", shape="ellipse", size=11, font_color="#FFFFFF")
    d.box("coord", 150, 330, 210, 84, ["Coordinator", "hiểu câu hỏi, chọn tác tử", "qwen3.5:4b, lược đồ"], "yellow")
    d.edge("start", "coord", [(110, 372), (150, 372)])
    d.box("rag", 430, 60, 360, 270, ["RAG Agent"], "panel", shape="panel", size=14)
    d.box("ret", 450, 100, 320, 60, ["retrieve(query, doc_ids)", "hybrid 40 + 40 → RRF → rerank → 5"], parent="rag", size=12)
    d.box("ctx", 450, 175, 320, 50, ["assemble_context: con → cha, [S1]…[S5]"], parent="rag", size=12)
    d.box("ans", 450, 240, 320, 56, ["answer(question, evidence, feedback)", "qwen3.5:9b"], parent="rag", size=12)
    d.edge("ret", "ctx", [(610, 160), (610, 175)])
    d.edge("ctx", "ans", [(610, 225), (610, 240)])
    d.text(440, 300, 340, 26, "sở hữu kho tài liệu: D1, D2, D3", BLUE, 10)
    d.box("ana", 430, 400, 360, 300, ["Analyst Agent"], "panel", shape="panel", size=14)
    d.box("plan", 450, 440, 320, 56, ["plan", "qwen3.5:4b, lược đồ ToolPlan"], parent="ana", size=12)
    d.box("tools", 450, 516, 320, 70, ["run_tools (tất định)", "outline · calculate · compare", "extract_table · risk_check"],
          parent="ana", size=12)
    d.box("intp", 450, 606, 320, 56, ["interpret", "qwen3.5:9b"], parent="ana", size=12)
    d.edge("plan", "tools", [(610, 496), (610, 516)])
    d.edge("tools", "intp", [(610, 586), (610, 606)])
    d.text(440, 668, 340, 26, "lấy bằng chứng qua RAG.retrieve(…, doc_ids)", BLUE, 10)
    d.edge("coord", "rag", [(360, 350), (395, 350), (395, 130), (430, 130)])
    d.text(240, 255, 150, 34, "lookup, extract", GREY, 10, "right")
    d.edge("coord", "ana", [(360, 394), (395, 394), (395, 468), (430, 468)])
    d.text(200, 474, 190, 46, "aggregate, calculate, compare,\nrisk_review, summarize", GREY, 10, "right")
    d.box("val", 860, 200, 300, 330, ["Validator Agent"], "panel", shape="panel", size=14)
    d.box("num", 880, 240, 260, 56, ["check_numbers", "tất định, không gọi mô hình"], parent="val", size=12)
    d.box("ver", 880, 320, 260, 56, ["verify_claims", "mô hình, lược đồ"], parent="val", size=12)
    d.box("gate", 880, 400, 260, 76, ["quality_gate", "luật cố định:", "accept · retry · give_up"], "yellow", parent="val",
          size=12)
    d.edge("num", "ver", [(1010, 296), (1010, 320)])
    d.edge("ver", "gate", [(1010, 376), (1010, 400)])
    d.edge("rag", "val", [(790, 268), (825, 268), (825, 300), (860, 300)])
    d.text(796, 236, 60, 30, "Draft,\nevidence", GREY, 10, "left")
    d.edge("ana", "val", [(790, 634), (825, 634), (825, 450), (860, 450)])
    d.text(796, 640, 70, 30, "Draft,\ntool_results", GREY, 10, "left")
    d.edge("val", "rag", [(1010, 200), (1010, 30), (610, 30), (610, 60)], RED, dashed=True)
    d.edge("val", "ana", [(1010, 530), (1010, 730), (610, 730), (610, 700)], RED, dashed=True)
    d.text(620, 8, 380, 20, "retry khi round < 2: tìm thêm bằng chứng, soạn lại với phản hồi", RED, 10, "left")
    d.text(620, 734, 380, 20, "retry khi round < 2: lấy thêm bằng chứng, diễn giải lại", RED, 10, "left")
    d.box("fin", 1200, 336, 170, 64, ["finalize", "trích dẫn, cảnh báo, lưu"], "green")
    d.edge("val", "fin", [(1160, 368), (1200, 368)])
    d.text(1162, 330, 50, 34, "accept,\ngive_up", GREY, 9, "left")
    d.box("end", 1245, 450, 80, 44, ["END"], "dark", shape="ellipse", size=11, font_color="#FFFFFF")
    d.edge("fin", "end", [(1285, 400), (1285, 450)])
    save(d, "p4_agents_graph")


def erd_physical():
    d = Diagram(1680, 710, "physical ERD")
    xs = {"A": 20, "B": 360, "C": 700, "D": 1040, "E": 1380}
    tables = [
        ("conv", "A", 40, ["conversations", "PK id", "FK tenant_id", "title, created_at, updated_at"]),
        ("turns", "A", 170, ["turns", "PK id", "FK conversation_id", "seq, question, question_type",
                             "answer, status, warnings", "config, latency_ms, created_at"]),
        ("cites", "A", 330, ["citations", "PK, FK turn_id", "PK label", "chunk_id → Qdrant",
                             "FK document_id, version_id", "sentence_index, verdict"]),
        ("scope", "A", 480, ["turn_scope", "PK, FK turn_id", "PK, FK document_id"]),
        ("ten", "B", 40, ["tenants", "PK id", "name, created_at"]),
        ("docs", "B", 170, ["documents", "PK id", "FK tenant_id, genre_id", "FK current_version_id",
                            "title, doc_number, parties", "issued / effective / expiry_date", "validity_status, status",
                            "created_at, updated_at"]),
        ("rel", "B", 360, ["document_relations", "FK source_document_id", "FK target_document_id (rỗng được)",
                           "target_number, relation_type", "scope, effective_date"]),
        ("genres", "C", 40, ["genres", "PK id", "name, structure_levels", "detection_rules"]),
        ("ver", "C", 170, ["document_versions", "PK id (mã băm nội dung)", "FK document_id", "seq, status, error",
                           "file_name, file_ext, file_size", "stored_path, pages, ingested_at"]),
        ("nodes", "C", 330, ["structure_nodes", "PK id", "FK version_id, parent_id", "level, number, title",
                             "ordinal, page_start, page_end", "quoted_from"]),
        ("jobs", "C", 500, ["ingest_jobs", "PK id", "FK tenant_id, document_id", "file_name, status, stage",
                            "progress, error, created_at"]),
        ("rules", "D", 40, ["review_rules", "PK id", "FK tenant_id, genre_id", "name, condition (JSON)",
                            "severity, basis, enabled"]),
        ("runs", "D", 330, ["review_runs", "PK id", "FK version_id", "started_at, status"]),
        ("finds", "D", 440, ["findings", "PK id", "FK run_id, rule_id", "description, severity, value"]),
        ("fchunks", "D", 560, ["finding_chunks", "PK, FK finding_id", "PK chunk_id → Qdrant"]),
        ("qd", "E", 170, ["Qdrant: vtagent_chunks_<cấu hình>", "id = chunk_id (UUID5)", "dense 1024 cosine,",
                          "sparse BM25 (IDF)", "tenant_id, document_id,", "version_id, node_id, is_current",
                          "genre, source, page, index", "section, header, text", "parent_id, parent_text"]),
    ]
    h = {}
    for cid, col, y, lines in tables:
        h[cid] = 16 + 15 * len(lines)
        d.box(cid, xs[col], y, 260, h[cid], lines, "store" if cid == "qd" else "node", shape="rect", size=12,
              align="left")
    bottom = {cid: y + h[cid] for cid, _, y, _ in tables}

    def rel(src, dst, pts, c1, c2, dashed=False):
        d.edge(src, dst, pts, arrow=False, dashed=dashed)
        (x1, y1), (x2, y2) = pts[0], pts[-1]
        for (x, y), (px, py), c in [((x1, y1), pts[1], c1), ((x2, y2), pts[-2], c2)]:
            dx = 6 if px >= x else -18
            dy = 4 if py > y else (-20 if py < y else -18)
            d.text(x + dx, y + dy, 14, 16, c, RED, 11, "left", bold=True)

    rel("conv", "turns", [(150, bottom["conv"]), (150, 170)], "1", "n")
    rel("turns", "cites", [(150, bottom["turns"]), (150, 330)], "1", "n")
    rel("turns", "scope", [(20, 230), (8, 230), (8, 510), (20, 510)], "1", "n")
    rel("docs", "cites", [(360, 280), (310, 280), (310, 380), (280, 380)], "1", "n")
    rel("docs", "scope", [(360, 292), (325, 292), (325, 505), (280, 505)], "1", "n")
    rel("ten", "docs", [(490, bottom["ten"]), (490, 170)], "1", "n")
    rel("genres", "docs", [(700, 100), (640, 100), (640, 200), (620, 200)], "1", "n")
    rel("docs", "ver", [(620, 225), (700, 225)], "1", "n")
    d.text(636, 208, 60, 16, "có", GREY, 10, "left")
    rel("docs", "ver", [(620, 262), (700, 262)], "1", "1", dashed=True)
    d.text(628, 264, 70, 16, "hiện hành", GREY, 10, "left")
    rel("docs", "rel", [(440, bottom["docs"]), (440, 360)], "1", "n")
    d.text(446, 330, 60, 16, "nguồn", GREY, 10, "left")
    rel("docs", "rel", [(560, bottom["docs"]), (560, 360)], "1", "n")
    d.text(566, 330, 60, 16, "đích", GREY, 10, "left")
    rel("ver", "nodes", [(830, bottom["ver"]), (830, 330)], "1", "n")
    rel("nodes", "nodes", [(960, 350), (990, 350), (990, 380), (960, 380)], "1", "n")
    d.text(994, 357, 50, 16, "cha–con", GREY, 10, "left")
    rel("genres", "rules", [(960, 70), (1040, 70)], "1", "n")
    rel("ver", "runs", [(960, 255), (1005, 255), (1005, 355), (1040, 355)], "1", "n")
    rel("rules", "finds", [(1300, 90), (1335, 90), (1335, 470), (1300, 470)], "1", "n")
    rel("runs", "finds", [(1170, bottom["runs"]), (1170, 440)], "1", "n")
    rel("finds", "fchunks", [(1170, bottom["finds"]), (1170, 560)], "1", "n")
    d.edge("qd", "ver", [(1380, 210), (960, 210)], arrow=False, dashed=True)
    d.text(1050, 190, 300, 18, "version_id: khóa logic giữa hai kho", BLUE, 10, "left")
    d.text(20, 640, 1000, 60, "Mọi bảng gốc (documents, conversations, review_rules, ingest_jobs) mang tenant_id → tenants;\n"
           "chỉ vẽ một đường để sơ đồ dễ đọc. Đường nét đứt: không có khóa ngoại thật, ứng dụng tự giữ nhất quán.\n"
           "Thực thể Tệp gốc (1 – 1 với Phiên bản) được gộp vào bảng document_versions.", GREY, 11, "left")
    save(d, "p4_erd_physical")


def sequence(name, title, parts, msgs, frames=(), width=1500, step=36, top=90, notes=()):
    """parts: [(id, label)]; msgs: (src, dst, label, kind) with kind call | ret | self.
    frames: (label, first_msg, last_msg, left_part, right_part)."""
    n = len(parts)
    gap = (width - 80) / n
    cx = {pid: 40 + gap * i + gap / 2 for i, (pid, _) in enumerate(parts)}
    height = top + step * (len(msgs) + 1) + 40 + 40 * len(notes)
    d = Diagram(width, height, title)
    for pid, label in parts:
        w = min(gap - 14, 170)
        d.box(pid, cx[pid] - w / 2, 20, w, 50, label.split("\n"), "blue", size=12)
        d.edge(None, None, [(cx[pid], 70), (cx[pid], height - 30 - 40 * len(notes))], "#9AA5B1", dashed=True,
               width=1, arrow=False)
    ys = []
    for k, (src, dst, label, kind) in enumerate(msgs):
        y = top + step * k + 20
        ys.append(y)
        if kind == "self":
            x = cx[src]
            d.edge(None, None, [(x, y - 8), (x + 30, y - 8), (x + 30, y + 8), (x + 4, y + 8)], GREY, width=1.2)
            d.text(x + 36, y - 9, gap * 1.6, 18, label, "#1A1A1A", 10, "left")
        else:
            x1, x2 = cx[src], cx[dst]
            d.edge(None, None, [(x1, y), (x2, y)], BLUE if kind == "call" else GREY, dashed=kind == "ret",
                   width=1.2)
            left = min(x1, x2)
            d.text(left + 6, y - 19, abs(x2 - x1) - 12, 18, label, "#1A1A1A", 10, "center")
    for label, first, last, lp, rp in frames:
        x0, x1 = cx[lp] - gap / 2 + 8, cx[rp] + gap / 2 - 8
        y0, y1 = ys[first] - 30, ys[last] + 14
        d.edge(None, None, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], RED, dashed=True, width=1,
               arrow=False)
        d.text(x0 + 4, y0 + 1, 400, 16, label, RED, 10, "left", bold=True)
    for k, s in enumerate(notes):
        d.text(40, height - 40 * (len(notes) - k) - 14, width - 80, 36, s, GREY, 11, "left")
    save(d, name)


def sequences():
    sequence("p4_seq_query", "query sequence", [
        ("u", "Giao diện web"), ("api", "API"), ("g", "Đồ thị truy vấn\nCoordinator"), ("rag", "RAG Agent"),
        ("q", "Qdrant"), ("o", "Ollama"), ("v", "Validator"), ("db", "SQLite")], [
        ("u", "api", "POST /conversations/{id}/turns", "call"),
        ("api", "db", "tạo lượt, trạng thái processing", "call"),
        ("api", "u", "200 SSE: stage, bản nháp", "ret"),
        ("api", "g", "chạy đồ thị (tenant, câu hỏi, lịch sử)", "call"),
        ("g", "o", "định tuyến: 4b, RoutingDecision", "call"),
        ("g", "rag", "retrieve(query, doc_ids)", "call"),
        ("rag", "o", "vector truy vấn (bge-m3)", "call"),
        ("rag", "q", "hybrid 40 + 40, lọc tenant", "call"),
        ("rag", "rag", "RRF, rerank 40 → 5, lắp ngữ cảnh", "self"),
        ("rag", "o", "soạn câu trả lời (9b)", "call"),
        ("rag", "v", "Draft + EvidencePack", "call"),
        ("v", "v", "check_numbers", "self"),
        ("v", "o", "verify_claims (lược đồ)", "call"),
        ("v", "rag", "retry: phản hồi các ý thiếu", "call"),
        ("rag", "v", "Draft vòng 2", "ret"),
        ("v", "g", "final: accept hoặc give_up", "ret"),
        ("g", "db", "lưu câu trả lời, trích dẫn (một giao dịch)", "call"),
        ("api", "u", "SSE: câu trả lời đã kiểm", "ret"),
    ], frames=[("alt [gate = retry và round < 2]", 13, 14, "rag", "v")],
        notes=["Luồng SSE theo UI Message Stream v1 (SDD 9.3): data-stage sau mỗi nút; token bản nháp là reasoning; câu trả lời "
               "đã kiểm chứng là text. Câu hỏi phân tích đi qua Analyst Agent thay cho RAG Agent, cùng trình tự với Validator."])
    sequence("p4_seq_ingest", "ingest sequence", [
        ("u", "Giao diện web"), ("api", "API"), ("w", "Worker\n(hàng đợi)"), ("rag", "RAG Agent\nluồng nạp"),
        ("f", "Kho tệp"), ("db", "SQLite"), ("o", "Ollama"), ("q", "Qdrant")], [
        ("u", "api", "POST /documents (multipart)", "call"),
        ("api", "api", "kiểm tra đuôi, chữ ký tệp, kích thước", "self"),
        ("api", "db", "tạo ingest_job (queued)", "call"),
        ("api", "u", "202 {job_id}; SSE /jobs/{id}/events", "ret"),
        ("api", "w", "đưa tác vụ vào hàng đợi", "call"),
        ("w", "rag", "ingest(tệp, tenant)", "call"),
        ("rag", "db", "tra mã băm nội dung (BR03)", "call"),
        ("rag", "w", "duplicate: trả định danh có sẵn", "ret"),
        ("rag", "rag", "trích văn bản; kiểm tra lớp văn bản (BR02)", "self"),
        ("rag", "rag", "thể loại, cấu trúc, siêu dữ liệu, quan hệ", "self"),
        ("rag", "rag", "chia đoạn cha–con, tiêu đề ngữ cảnh", "self"),
        ("rag", "o", "vector các đoạn (bge-m3, theo lô)", "call"),
        ("rag", "q", "upsert đoạn (payload tenant, version)", "call"),
        ("rag", "f", "chép tệp gốc", "call"),
        ("rag", "db", "documents, versions, structure_nodes (một giao dịch)", "call"),
        ("w", "db", "ingest_job: done", "call"),
        ("api", "u", "SSE: done {document_id, genre}", "ret"),
    ], frames=[("alt [đã có trong kho]", 7, 7, "w", "db")],
        notes=["Mỗi bước nạp ghi stage và progress vào ingest_jobs; API đọc bảng này để đẩy sự kiện. Lỗi ở một bước: "
               "job failed kèm lý do, tệp khác trong lô vẫn được xử lý (NFR-10)."])
    sequence("p4_seq_delete", "delete sequence", [
        ("u", "Giao diện web"), ("api", "API"), ("s", "Dịch vụ tài liệu\n(RAG Agent)"), ("db", "SQLite"),
        ("q", "Qdrant"), ("f", "Kho tệp")], [
        ("u", "api", "DELETE /documents/{id} (đã xác nhận)", "call"),
        ("api", "s", "delete(document_id)", "call"),
        ("s", "db", "documents.status = deleting", "call"),
        ("s", "q", "xóa điểm có document_id = id", "call"),
        ("s", "f", "xóa tệp gốc của mọi phiên bản", "call"),
        ("s", "db", "xóa danh mục (một giao dịch)", "call"),
        ("s", "api", "đã xóa", "ret"),
        ("api", "u", "204 No Content", "ret"),
    ], width=1300, notes=[
        "Thứ tự xóa: nội dung (Qdrant, tệp) trước, danh mục sau. Lỗi giữa chừng chỉ để lại tài liệu ở trạng thái "
        "deleting, không còn nội dung để truy xuất; tác vụ dọn dẹp khi khởi động làm tiếp từ bước xóa trong Qdrant."])


def deployment():
    d = Diagram(1440, 640, "deployment")
    d.box("pc", 20, 20, 880, 600, ["Máy Windows 11 (máy tham chiếu: Ryzen 7 8845HS, Radeon 780M, 32 GB RAM)"],
          "panel", shape="panel", size=13)
    d.box("br", 50, 70, 200, 70, ["Trình duyệt", "giao diện web (React)"], "node", parent="pc")
    d.box("app", 300, 60, 570, 250, ["Tiến trình VTAgent: Python, uvicorn, 127.0.0.1:8000"], "panel", shape="panel",
          parent="pc", size=12)
    for i, lines in enumerate([["FastAPI", "API, tệp tĩnh giao diện"], ["Worker nạp", "cùng tiến trình"],
                               ["LangGraph, agents/, core/"], ["ONNX Runtime", "reranker trên CPU"]]):
        d.box(f"a{i}", 320 + (i % 2) * 275, 100 + (i // 2) * 100, 255, 80, lines, "blue", parent="app", size=12)
    d.box("oll", 300, 350, 270, 120, ["Ollama 127.0.0.1:11434", "tăng tốc Vulkan, Radeon 780M", "qwen3.5:9b, qwen3.5:4b,",
                                      "bge-m3"], "yellow", parent="pc", size=12)
    d.box("qd", 600, 350, 270, 120, ["Qdrant 127.0.0.1:6333", "Docker Desktop (WSL2)", "hoặc nhúng trong tiến trình",
                                     "telemetry tắt"], "yellow", parent="pc", size=12)
    d.box("data", 50, 350, 220, 120, ["Thư mục data/", "vtagent.db (SQLite)", "files/ (tệp gốc)", "logs/"], "data",
          shape="rect", parent="pc", size=12)
    d.edge("br", "app", [(250, 105), (300, 105)], both=True)
    d.text(252, 80, 50, 20, "HTTP, SSE", GREY, 9, "left")
    d.edge("app", "oll", [(435, 310), (435, 350)], both=True)
    d.edge("app", "qd", [(735, 310), (735, 350)], both=True)
    d.edge("app", "data", [(330, 310), (330, 330), (160, 330), (160, 350)], both=True)
    d.text(40, 490, 840, 110, "Mọi dịch vụ chỉ lắng nghe 127.0.0.1; không có kết nối ra ngoài khi vận hành (NFR-01).\n"
           "Mô hình, ảnh Docker và gói Python chỉ được tải một lần lúc cài đặt.\n"
           "Một lệnh cài đặt (NFR-14): kiểm tra Ollama, kéo mô hình, tạo môi trường Python,\n"
           "tải reranker ONNX, khởi động Qdrant, đặt biến môi trường.", GREY, 11, "left")
    d.box("srv", 940, 20, 480, 600, ["Mở rộng sau: server nội bộ nhiều tenant (SRS Phụ lục A)"], "panel", shape="panel",
          size=13)
    for i, lines in enumerate([["Reverse proxy, TLS"], ["API × N", "xác thực, RBAC"], ["PostgreSQL", "Row-Level Security"],
                               ["Qdrant", "lọc tenant, không gian"], ["vLLM / llama-server", "GPU rời"],
                               ["LDAP/AD hoặc", "tài khoản cục bộ"]]):
        d.box(f"s{i}", 960 + (i % 2) * 225, 70 + (i // 2) * 120, 210, 90, lines, "node", planned=True, parent="srv",
              size=12)
    d.text(960, 440, 440, 120, "Thay SQLite bằng PostgreSQL, Ollama bằng máy phục vụ có\nbatching trên GPU rời; "
           "thêm xác thực và phân quyền.\nKiến trúc phân tầng, đồ thị tác tử và lược đồ Qdrant\ngiữ nguyên nhờ tenant_id "
           "có sẵn (NFR-16).", GREY, 11, "left")
    save(d, "p4_deployment")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    layers()
    agents()
    erd_physical()
    sequences()
    deployment()
