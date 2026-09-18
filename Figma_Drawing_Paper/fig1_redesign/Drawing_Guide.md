# Fig. 1 — bản ít chữ

Style lấy từ ảnh tham khảo; nội dung lấy từ Fig. 1 và Introduction của paper/main.tex.

## Chỉnh sửa

- Mở fig1_degro.drawio trong draw.io để sửa từng hộp, text và mũi tên. Mũi tên đặt theo tọa độ; khi di chuyển hộp có thể cần nối lại.
- Import fig1_degro.svg vào Figma làm bản vector tham chiếu để vẽ lại.
- fig1_preview.png là ảnh xem trước.

## Thiết kế

Canvas 1500 × 700; ba cột bằng nhau, đường phân cách chấm. Arial, tiêu đề 32 px, nhãn 25–29 px. Màu vàng #FFF2CC, lam #D9E2F3, lá #CAE5B2. Nền trắng; check xanh và cross đỏ.

Execution-level: Q → LLM Program → Execute Program → Runtime Check → Runs / Fails.

Outcome-level: Q → LLM Program → Extract Answer → Answer Matching → Correct / Incorrect.

Determinacy-level: Q → LLM Program → Target Determinacy Check → hai hộp q=4 và q=6, dấu ≠ → Grounded Repair / Abstain.

Cột DeGro minh họa nhánh ambiguous, không phải toàn bộ pipeline. Hai hộp là hai giá trị target của hai feasible models, không phải hai đáp án dự đoán. Ví dụ paper: a,b nguyên không âm; F: a+b=10; target q=a. Hai assignment (4,6) và (6,4) cho q=4 và q=6. Nếu source có “A receives two more than B”, constraint a=b+2 có căn cứ; nếu không có, abstain.

Công thức hai bản sao, feasibility check, trạng thái unknown/unsupported và chi tiết acceptance gate được bỏ khỏi hình để giữ thoáng. Các bước đó vẫn thuộc method. Repair chỉ được nhận khi có source support và vượt qua các gate; hình không tuyên bố mọi ambiguity đều sửa được.

## Caption

**Figure 1: Three levels of executable mathematical reasoning evaluation.** Execution checks whether a program runs; outcome evaluation checks its final answer. DeGro diagnoses target ambiguity through two feasible models with different target values (illustrated by q=4 and q=6), then attempts source-grounded repair with deterministic acceptance gates or abstains. Target determinacy is relative to the encoded specification and does not establish faithfulness to the source problem.

Bản ít chữ đã được chèn tạm vào main.tex dưới dạng figure một cột theo yêu cầu; hình nằm ở cột phải trang 1 trong bản PDF đã biên dịch.
