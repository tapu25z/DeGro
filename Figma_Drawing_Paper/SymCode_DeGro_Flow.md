# Flow của SymCode + DeGro

## Mô tả ngắn

SymCode biến đề toán thành chương trình Python/SymPy và chạy chương trình để lấy đáp án. DeGro không thay thế SymCode; nó đứng sau SymCode để kiểm tra xem các ràng buộc mà chương trình đã mã hóa có thật sự xác định duy nhất đại lượng cần tìm hay không. Nếu mô hình còn thiếu ràng buộc, DeGro chỉ cho phép bổ sung một điều kiện có căn cứ trong đề bài; nếu không thể sửa an toàn, hệ thống từ chối sửa.

## Pipeline

### 1. Input: đề toán

Hệ thống nhận một đề toán bằng ngôn ngữ tự nhiên.

### 2. SymCode sinh chương trình

LLM đọc đề và sinh một chương trình Python dùng SymPy. Chương trình chứa:

- các biến toán học;
- các phương trình và điều kiện;
- cách giải bằng SymPy;
- bước kiểm tra nghiệm;
- lệnh in đáp án cuối cùng.

### 3. Thực thi và debug chương trình

Hệ thống chạy chương trình SymPy.

- Nếu chương trình chạy thành công, hệ thống thu được `SymCode code` và `SymCode answer`.
- Nếu có lỗi cú pháp hoặc lỗi thực thi, SymCode+ gửi lỗi lại cho LLM để sửa code rồi chạy lại.
- Nếu code vẫn không chạy được, pipeline dừng với lỗi thực thi.

### 4. Chuyển code thành ModelSpec

Adapter đọc chương trình đã chạy và trích xuất mô hình khai báo gồm:

- variables: các biến và miền giá trị;
- constraints: các ràng buộc thực sự được code sử dụng;
- target: biểu thức mà bài toán yêu cầu tìm.

Mỗi constraint phải liên kết với một đoạn trong đề bài và một đoạn trong code. Adapter chỉ trích xuất mô hình; nó không được dùng đáp án đã in để tạo thêm constraint.

Nếu code không thể chuyển sang ngôn ngữ constraint mà DeGro hỗ trợ, hệ thống không kiểm tra được bằng DeGro và giữ đáp án SymCode+ làm fallback.

### 5. Z3 kiểm tra tính khả thi

ModelSpec được biên dịch thành các biểu thức Z3. Z3 kiểm tra xem toàn bộ constraint có ít nhất một nghiệm hay không.

- `SAT`: mô hình có nghiệm, tiếp tục kiểm tra determinacy.
- `UNSAT`: các constraint mâu thuẫn, kết quả là `INCONSISTENT`.
- `UNKNOWN`: Z3 không kết luận được trong giới hạn cho phép.
- `NOT_SUPPORTED`: biểu thức không thuộc phần ngôn ngữ mà compiler hỗ trợ.

### 6. Z3 kiểm tra target determinacy

DeGro tạo hai bản sao độc lập của cùng một ModelSpec:

`F(x₁) ∧ F(x₂) ∧ target(x₁) ≠ target(x₂)`

Z3 được hỏi liệu có thể tồn tại hai nghiệm đều thỏa các constraint nhưng cho hai giá trị target khác nhau hay không.

- Nếu truy vấn là `UNSAT`, không tồn tại hai giá trị target khác nhau. Target là `DETERMINATE`, vì vậy hệ thống giữ và trả đáp án SymCode+.
- Nếu truy vấn là `SAT`, Z3 tìm được hai nghiệm có target khác nhau. ModelSpec là `AMBIGUOUS` và được chuyển sang bước repair.
- Nếu truy vấn là `UNKNOWN`, DeGro không được phép tuyên bố target là duy nhất.

### 7. LLM đề xuất grounded repair

LLM nhận đề bài gốc, ModelSpec hiện tại và verdict `AMBIGUOUS`. LLM chỉ được chọn một trong hai hành động:

- `ADD_CONSTRAINT`: thêm tối đa một constraint bị thiếu và chỉ ra chính xác đoạn văn trong đề hỗ trợ constraint đó;
- `ABSTAIN`: không thêm constraint nếu đề bài không cung cấp đủ căn cứ.

LLM không được tự đoán một giả thiết hợp lý và không được thêm trực tiếp đáp án cuối làm constraint.

### 8. Deterministic repair gate

Constraint do LLM đề xuất chỉ được chấp nhận khi vượt qua tất cả kiểm tra sau:

1. Có nguồn hỗ trợ chính xác trong đề bài, hoặc là một quy tắc miền toán học được cho phép.
2. Biên dịch được sang Z3.
3. Không làm mô hình trở nên mâu thuẫn.
4. Không phải constraint dư thừa đã suy ra được từ mô hình cũ.
5. Sau khi thêm constraint, target được kiểm tra lại bằng Z3.

### 9. Output cuối cùng

- `PASS`: ModelSpec ban đầu đã determinate; trả đáp án SymCode+.
- `REPAIRED`: constraint được chấp nhận và target trở thành determinate; trả giá trị target do Z3 xác nhận.
- `ABSTAIN`: không có repair an toàn, repair bị gate từ chối, hoặc target vẫn ambiguous sau khi sửa.
- `FALLBACK`: adapter hoặc verifier không hỗ trợ trường hợp đó; giữ kết quả SymCode+ nhưng không có chứng nhận determinacy từ DeGro.
- `ERROR`: chương trình SymCode không thực thi thành công hoặc pipeline gặp lỗi hệ thống.

## Dòng flow ngắn để đưa vào hình

`Math Problem → SymCode generates SymPy code → Execute / Debug → Code + Answer → Extract ModelSpec → Z3 Feasibility Check → Z3 Target-Determinacy Check`

Sau determinacy check:

- `DETERMINATE → PASS → SymCode+ Answer`
- `AMBIGUOUS → Grounded LLM Repair → Deterministic Gate → Z3 Recheck → REPAIRED or ABSTAIN`
- `INCONSISTENT / UNKNOWN / NOT_SUPPORTED → No DeGro certificate → FALLBACK or STOP`

## Ý nghĩa của hai thành phần

- **SymCode** chịu trách nhiệm tạo và chạy lời giải có thể thực thi.
- **DeGro** chịu trách nhiệm kiểm tra xem mô hình phía sau lời giải có xác định duy nhất target hay không, sau đó repair có căn cứ hoặc abstain.

Vì vậy, chương trình chạy thành công chưa phải là bằng chứng rằng formalization đầy đủ. DeGro bổ sung lớp kiểm tra này sau bước thực thi của SymCode.
