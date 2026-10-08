# ALG514 — kiểm tra lần chạy Nemotron 30B gần nhất

Nguồn: `alg514_30b_schema_20261003_232244.jsonl`.
Model: `nemotron-3-nano:30b`; `think=true`, `temperature=0`.
Thời điểm bắt đầu theo tên file: 03/10/2026 23:22:44; lần ghi cuối theo mtime: 23:54:53, giờ máy (Asia/Ho_Chi_Minh).

## Kết quả

| Luồng | Đúng / tổng | Accuracy | Lỗi API | Lỗi thực thi |
| --- | ---: | ---: | ---: | ---: |
| Direct | 494/499 | 99.00% | 0 | 0 |
| ModelSpec → Z3 | 494/499 | 99.00% | 0 | 0 |

- Đủ 998 bản ghi: 499 bài × 2 luồng; không trùng, thiếu hoặc thừa ID so với `data/alg514/alg514_supported.jsonl`.
- Hai luồng cùng đúng 493 bài, cùng sai theo gold 4 bài. Direct thắng riêng bài 3623; ModelSpec thắng riêng bài 6525.
- ModelSpec có 489 bài DETERMINATE ban đầu, 9 AMBIGUOUS và 1 NOT_SUPPORTED. Repair thành công 8/9 bài, cả 8 khớp gold; 1 bài không tìm được repair hợp lệ.
- Trạng thái cuối ModelSpec: 497 DETERMINATE, 1 NOT_SUPPORTED, 1 NO_ADMISSIBLE_REPAIR_FOUND.
- Một lần sửa schema thành công ở bài 3394: bỏ biểu thức conditional không được compiler hỗ trợ. Không còn lỗi compiler cuối cùng.
- Tính lại điểm của cả 998 bản ghi: không có sai khác. Chạy lại Z3 trên 499 specification cuối cùng: trạng thái và giá trị khớp kết quả lưu. Với NO_ADMISSIBLE_REPAIR_FOUND, specification vẫn AMBIGUOUS như dự kiến.

## Các bài bị chấm sai

| ID | Direct | ModelSpec → Z3 | Nhận xét từ đề và output |
| --- | --- | --- | --- |
| 2196 | ≈31.06856, 49.709695 | ≈31.06856, 49.709695 | Gold là 50, 80 km/h nhưng đề hỏi vận tốc freight train bằng mph; model chuyển cả hai sang mph. Khác biệt đơn vị với gold. Lần này specification đã có hệ số 3 giờ đúng. |
| 2559 | Hai chuỗi rỗng | NOT_SUPPORTED | Dữ kiện nói House, câu hỏi nói Senate. Gold 202, 232 giải bài House; dữ kiện không xác định Senate. |
| 3623 | 2.25, 2.5 — đúng | 4.75 — sai | Hệ phương trình đúng nhưng ModelSpec dùng target `x+y`, trả tổng thay vì hai giá riêng theo gold. |
| 6004 | 1/5 | 1/5 | Cả hai trả tỷ lệ lợi nhuận theo giá bán; gold đòi số tiền lợi nhuận 11. Đề dùng “amount of profit”: cần trả lượng tiền theo cách hiểu của gold. |
| 6072 | 89 | NO_ADMISSIBLE_REPAIR_FOUND | 89 là số áo nguyên tối thiểu để không lỗ; gold 88.23529 là điểm hòa vốn liên tục. Spec dùng Int và bất đẳng thức nên có nhiều nghiệm. Hai repair thêm đẳng thức bị từ chối vì INCONSISTENT. Bài ngưỡng/tối ưu ngoài phạm vi prompt, nhưng model vẫn khởi tạo SUPPORTED. |
| 6525 | 5.4, 0.4 — bị chấm sai | 3775/697, 275/697 — được chấm đúng | Direct làm tròn theo yêu cầu “nearest tenth”; gold và ModelSpec dùng nghiệm chưa làm tròn. Điểm benchmark không phản ánh đầy đủ yêu cầu định dạng của đề. |

## So với lần chạy ngay trước

So sánh với `alg514_30b_schema_20261003_215420.jsonl`:

- Direct giữ 494/499.
- ModelSpec tăng từ 492/499 (98.60%) lên 494/499 (99.00%), tăng 2 bài, khoảng 0.40 điểm phần trăm.
- ModelSpec sửa được các bài 1315, 3648, 6334; bài 6004 chuyển từ đúng sang sai.
- Lần sửa schema giảm từ 32 xuống 1; số bài cần grounded repair giảm từ 17 xuống 9. Đây là quan sát giữa hai lần chạy, không xác lập riêng nguyên nhân cải thiện.

## Giới hạn cách chấm

Tất cả bản ghi dùng `alg514_compatible`: đáp án dự đoán được ghép với một tập con của `gold_solutions`, tolerance tuyệt đối/tương đối 1e-3; không kiểm tra thứ tự hoặc bắt buộc trả đủ mọi nghiệm trong gold. Có 98 bài ở mỗi luồng được chấm đúng với ít giá trị hơn số phần tử gold. Điều này có thể phù hợp khi đề chỉ hỏi một đại lượng nhưng gold lưu cả nghiệm hệ; không tự động là lỗi hoặc căn cứ để đổi điểm.

Vì vậy 99.00% là điểm theo scorer hiện tại, chưa phải xác minh toàn bộ ngữ nghĩa, đơn vị, thứ tự và làm tròn của từng câu trả lời. Kiểm tra lại Z3 xác nhận specification đã lưu, không chứng minh specification diễn đạt đúng đề.

Không chạy inference mới và không thay đổi dữ liệu, gold, script hoặc output gốc.
