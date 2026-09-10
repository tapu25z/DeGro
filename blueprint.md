# TargetCheck: Target-Determinacy Verification and Grounded Repair for Executable Mathematical Reasoning

## 1. Ý tưởng trong một câu

**TargetCheck mở rộng SymCode bằng cách kiểm tra liệu formalization hiện tại có thực sự đủ để xác định duy nhất đại lượng mà bài toán hỏi hay không; nếu chưa đủ, solver tạo hai nghiệm cho target khác nhau làm bằng chứng để LLM sửa constraint bị bỏ sót, nhưng chỉ khi đề gốc có căn cứ cho constraint đó; nếu đề thật sự thiếu dữ kiện, hệ thống phải abstain thay vì tự bịa giả định.**

Điểm cốt lõi là:

\[
\boxed{
\text{Executable} \not\Rightarrow \text{Answer is justified}
}
\]

SymCode đã cho thấy lợi ích của việc chuyển mathematical reasoning sang executable SymPy code và báo cáo cải thiện tới 13.6 điểm phần trăm trên các benchmark như MATH-500 và OlympiadBench.

Nhưng một chương trình có thể:

- chạy không lỗi;
- solver tìm được nghiệm;
- thậm chí trả về một con số;

mà vẫn **không encode đầy đủ đề toán**.

TargetCheck nhắm đúng failure mode này.

---

# 2. Problem statement

Xét bài:

> Có 10 nhiệm vụ được chia cho A và B.  
> A nhận nhiều hơn B hai nhiệm vụ.  
> Hỏi A nhận bao nhiêu?

Formalization đúng:

\[
a,b\in\mathbb Z_{\ge0}
\]

\[
a+b=10
\]

\[
a=b+2
\]

Target:

\[
q(a,b)=a.
\]

Nhưng LLM có thể sinh:

\[
a+b=10
\]

và bỏ mất:

\[
a=b+2.
\]

Formalization này hoàn toàn hợp lệ về mặt syntax.

Solver không crash.

Nó thậm chí tìm được nghiệm.

Ví dụ:

\[
(a,b)=(4,6)
\]

hoặc:

\[
(a,b)=(6,4).
\]

Nhưng hai nghiệm cho target khác nhau:

\[
q(4,6)=4
\]

\[
q(6,4)=6.
\]

Do đó formalization hiện tại **không justify một answer duy nhất**.

Đây là loại lỗi mà execution checking đơn thuần không phát hiện được.

---

# 3. Nhưng vấn đề còn khó hơn: đề có thể thật sự thiếu dữ kiện

Xét bài:

> Có 10 nhiệm vụ được chia cho A và B.  
> Hỏi A nhận bao nhiêu?

Formalization:

\[
a+b=10.
\]

Target:

\[
q(a,b)=a.
\]

Vẫn có:

\[
(a,b)=(4,6)
\]

và:

\[
(a,b)=(6,4).
\]

Nhưng lần này formalization **không sai**.

Chính đề bài không cung cấp đủ thông tin.

Một refinement system ngây thơ có thể thấy ambiguity rồi tự thêm:

\[
a=b+2,
\]

hoặc:

\[
a=b,
\]

hoặc một assumption nào đó để cưỡng ép ra answer.

Đây chính là hành vi chúng ta muốn tránh.

Vì vậy TargetCheck không chỉ giải bài toán:

> “Có constraint nào thiếu khỏi formalization không?”

Mà giải câu khó hơn:

\[
\boxed{
\text{Constraint bị bỏ khỏi formalization,
hay nó vốn không tồn tại trong đề?}
}
\]

Đây nên là research question trung tâm của paper.

---

# 4. Research question

RQ chính:

> **Can solver-generated target-divergent witnesses help an LLM distinguish omitted mathematical constraints from genuine problem underspecification?**

RQ2:

> **Do concrete target-divergent witnesses provide more useful repair feedback than a generic message stating that the answer is non-unique?**

RQ3:

> **Can source-grounded repair reduce unsupported assumptions while preserving the ability to recover omitted constraints?**

RQ4:

> **Does the method generalize across model scales and model families?**

RQ4 chính là lý do việc chạy:

- GPT-OSS 20B;
- GPT-OSS 120B;
- Gemma 4 31B;

rất có giá trị.

---

# 5. Những gì paper KHÔNG claim

Không nên claim:

> “Chúng tôi phát minh ra checking uniqueness.”

Không.

Không claim:

> “Chúng tôi là người đầu tiên dùng solver feedback.”

Không.

Không claim:

> “Chúng tôi là người đầu tiên phát hiện missing constraints.”

Không.

ReLoop gần đây đã nghiên cứu silent failures trong NL-to-optimization, nơi code chạy và solver tìm feasible solution nhưng mathematical formulation vẫn sai; họ dùng solver-based parameter perturbation để phát hiện missing constraints/objective terms.

SymDiag cũng đã dùng symbolic verification, counterexamples và missing-premise indicators để diagnose reasoning failures.

Một work rất mới khác dùng minimal unsatisfiable cores để sửa trường hợp formalization bị over-constrained/UNSAT.

Novelty của TargetCheck phải hẹp và chính xác hơn:

> **Target-directed ambiguity certificates for distinguishing formalization omissions from genuine underspecification in executable mathematical reasoning.**

---

# 6. Formalization

Cho bài toán ngôn ngữ tự nhiên:

\[
P.
\]

LLM sinh mathematical formalization:

\[
F=(V,D,C,q)
\]

trong đó:

- \(V\): variables;
- \(D\): domains;
- \(C\): mathematical constraints;
- \(q(V)\): target expression mà bài yêu cầu.

Tập nghiệm:

\[
\operatorname{Sol}(F)
=
\{m \mid m\models D\land C\}.
\]

## Target determinacy

Ta gọi \(q\) **determinate under \(F\)** khi:

\[
\forall m_1,m_2\in \operatorname{Sol}(F),
\quad
q(m_1)=q(m_2).
\]

Lưu ý:

\[
|\operatorname{Sol}(F)|
\]

không cần bằng 1.

Chỉ target cần duy nhất.

Ví dụ:

\[
x=5,\qquad y\ge0.
\]

Có vô số nghiệm vì \(y\) tự do.

Nhưng nếu câu hỏi là:

\[
q=x,
\]

thì answer vẫn hoàn toàn xác định:

\[
q=5.
\]

Đây là distinction quan trọng giữa:

\[
\textbf{solution uniqueness}
\]

và:

\[
\boxed{\textbf{target determinacy}}.
\]

TargetCheck chỉ quan tâm cái thứ hai.

---

# 7. Target-divergent witness

Thay vì enumerate toàn bộ solution space, tạo hai bản sao của variables:

\[
V^{(1)},V^{(2)}.
\]

Kiểm tra:

\[
\Phi(F,q)=
F(V^{(1)})
\land
F(V^{(2)})
\land
q(V^{(1)})\neq q(V^{(2)}).
\]

Có ba kết quả.

### SAT

Có:

\[
m_1,m_2
\]

sao cho:

\[
m_1\models F,
\qquad
m_2\models F
\]

nhưng:

\[
q(m_1)\neq q(m_2).
\]

Hai model này là:

> **target-divergent witness pair**.

Chúng là bằng chứng máy kiểm chứng được rằng formalization hiện tại chưa đủ để xác định target.

### UNSAT

Không tồn tại hai model như vậy.

Suy ra:

\[
\forall m_1,m_2\models F,
q(m_1)=q(m_2).
\]

Target determinate theo formalization hiện tại.

### UNKNOWN / TIMEOUT

Không được kết luận unique.

Trả:

```text
UNKNOWN
```

hoặc fallback.

Đây rất quan trọng về soundness:

\[
\text{solver timeout}
\neq
\text{proof of uniqueness}.
\]

---

# 8. TargetCheck không phải full semantic verifier

Đây phải viết cực rõ trong paper.

Giả sử đề thật sự thiếu dữ kiện:

> \(a+b=10\). Find \(a\).

Nhưng LLM hallucinate:

\[
a+b=10
\]

\[
a=6.
\]

TargetCheck sẽ thấy:

\[
a
\]

được xác định duy nhất.

Nhưng formalization vẫn sai.

Do đó:

\[
\boxed{
\text{Target determinacy}
\neq
\text{semantic faithfulness}.
}
\]

Formal guarantee của TargetCheck chỉ là:

> nếu determinacy checker trả UNSAT, tất cả solutions của **formalization hiện tại** agree trên target.

Nó không chứng minh:

\[
F\equiv P.
\]

Đây là limitation phải chủ động nói.

Để giảm rủi ro này, ta thêm provenance cho constraints, nhưng cũng không claim provenance là formal semantic proof.

---

# 9. Structured SymCode

Thay vì để LLM chỉ sinh một cục Python khó phân tích, mình đề xuất chỉnh SymCode nhẹ thành:

```json
{
  "variables": [
    {
      "name": "a",
      "domain": "Int"
    },
    {
      "name": "b",
      "domain": "Int"
    }
  ],

  "constraints": [
    {
      "id": "c1",
      "expression": "a + b == 10",
      "source_span": "There are 10 tasks divided between A and B."
    }
  ],

  "target": "a"
}
```

Sau đó compiler deterministic tạo:

1. executable SymPy representation;
2. verifier representation.

Pipeline:

```text
Problem
   ↓
LLM
   ↓
ModelSpec
   ├────→ SymPy executor
   │
   └────→ TargetCheck verifier
```

Điều này tốt hơn việc bắt LLM generate hai chương trình độc lập vì nếu generate:

```text
SymPy code
```

và:

```text
Z3 code
```

riêng biệt thì hai representation có thể lại không đồng nhất.

Một `ModelSpec` chung làm source of truth sẽ sạch hơn.

---

# 10. Solver nào?

## SymPy

Giữ SymPy làm computational backend vì đó là tinh thần SymCode.

## Z3

Dùng Z3 cho target-determinacy checking.

Prototype đầu tiên chỉ support fragment dễ kiểm chứng:

\[
\text{integer/real variables}
\]

\[
\text{linear equality/inequality}
\]

\[
\text{finite domains}
\]

\[
\text{selected modular constraints}.
\]

Không cần support toàn bộ MATH-500.

Nếu gặp:

- transcendental expressions;
- unsupported functions;
- solver UNKNOWN;
- conversion failure;

TargetCheck trả:

```text
NOT_SUPPORTED
```

chứ không giả vờ verify.

Paper cần báo:

\[
\text{verification coverage}
\]

như một metric.

---

# 11. Pipeline hoàn chỉnh

```text
Natural-language mathematical problem P
                    │
                    ▼
           Structured SymCode
                    │
           variables / domains
           constraints / target
                    │
                    ▼
             Execution Check
                    │
        ┌───────────┴───────────┐
        │                       │
 execution error              success
        │                       │
        ▼                       ▼
 SymCode repair          TargetCheck
                                │
                     F₁ ∧ F₂ ∧ q₁ ≠ q₂
                                │
             ┌──────────────────┼──────────────────┐
             │                  │                  │
            SAT               UNSAT             UNKNOWN
             │                  │                  │
             ▼                  ▼                  ▼
     divergent witness       target            UNKNOWN
          pair m₁,m₂       determinate
             │
             ▼
       Grounded Diagnosis
             │
     ┌───────┴─────────┐
     │                 │
 supported           no supported
 missing constraint   condition
     │                 │
     ▼                 ▼
   repair         UNDERSPECIFIED
     │
     ▼
   re-check
```

---

# 12. Witness feedback

Giả sử solver tìm:

```text
Witness A
a = 4
b = 6

Witness B
a = 6
b = 4
```

Không hỏi LLM chung chung:

> “Formalization is wrong. Fix it.”

Mà cho một task có cấu trúc:

```text
Original problem:
...

Current constraints:
...

Target:
a

Both assignments satisfy the current constraints,
but give different target values.

Witness A:
a=4, b=6
target=4

Witness B:
a=6, b=4
target=6

Compare the witnesses against the original problem.

Return either:

ADD_CONSTRAINT:
- exact supporting source span
- missing mathematical constraint

or:

ABSTAIN:
- if no information in the source supports a missing constraint.
```

Output bắt buộc JSON:

```json
{
  "decision": "ADD_CONSTRAINT",
  "source_span": "A receives two more tasks than B.",
  "constraint": "a == b + 2"
}
```

hoặc:

```json
{
  "decision": "ABSTAIN"
}
```

Không cần LLM sinh essay dài.

Không cần lưu chain-of-thought.

---

# 13. Grounding gate

Candidate constraint \(c\) không được thêm ngay.

Ta kiểm:

### Parseable

\[
c
\]

phải compile được.

### Source evidence

`source_span` phải xuất hiện trong problem text, hoặc thuộc một tập domain semantics đã khai báo rõ.

Ví dụ:

```text
number of tasks
```

có thể justify:

\[
a,b\in\mathbb Z_{\ge0}.
\]

Ta có thể cho provenance type:

```text
EXPLICIT_TEXT
DOMAIN_SEMANTICS
```

Không cho:

```text
UNSUPPORTED_ASSUMPTION.
```

### Consistency

Phải có:

\[
SAT(F\land c).
\]

Nếu thêm constraint rồi formalization thành contradiction thì reject candidate.

### Non-redundancy

Nếu:

\[
F\models c
\]

thì candidate chẳng sửa gì cả.

Reject.

### Re-check target

Sau khi:

\[
F'=F\land c
\]

kiểm lại:

\[
F'_1\land F'_2
\land
q_1\neq q_2.
\]

Nếu UNSAT → repaired.

Nếu SAT → lấy witness pair mới và tiếp tục.

Đặt:

\[
K_{\max}=2
\]

cho paper đầu.

Một hoặc hai repair round là đủ cho scope hiện tại và giúp kiểm soát token cost.

---

# 14. Output của agent

Đừng ép mọi bài thành ANSWER.

Hệ thống có các trạng thái:

```text
ANSWER
UNDERSPECIFIED
INCONSISTENT
UNKNOWN
UNSUPPORTED
```

Đây là thiết kế quan trọng.

Một trustworthy mathematical agent phải được phép nói:

> Không đủ dữ kiện.

thay vì luôn phải trả một con số.

---

# 15. Benchmark chính: Paired Target-Determinacy Evaluation

Đây là experiment quan trọng nhất.

Ta cần tạo hai cases có:

\[
\boxed{\text{cùng formalization}}
\]

nhưng source text khác nhau.

## Case A — Formalization omission

Full problem:

```text
There are 10 tasks.
A receives two more tasks than B.
Find A.
```

Formalization bị lỗi:

\[
a+b=10.
\]

Expected:

```text
REPAIR
```

với:

\[
a=b+2.
\]

## Case B — Genuine underspecification

Problem:

```text
There are 10 tasks.
Find A.
```

Formalization giống hệt:

\[
a+b=10.
\]

Expected:

```text
ABSTAIN.
```

Do đó:

\[
F_A=F_B
\]

nhưng:

\[
P_A\neq P_B.
\]

Điều duy nhất cho phép system quyết định repair hay abstain là **grounding trong đề gốc**.

Đây là controlled experiment rất mạnh.

---

# 16. Không nên tự tạo toàn bộ benchmark: dùng MIRA-Math

MIRA-Math là benchmark tháng 7/2026 với 2,310 instances từ 22 mathematical families. Mỗi instance được tạo từ một complete latent mathematical state có unique answer; Agent A nhận một view bị thiếu đúng một atomic fact cần thiết, Agent B giữ fact đó, và dataset cung cấp deterministic generators, validators, exact answer verifiers cùng machine-readable `minimal_hint_spec`.

Nó cực hợp với TargetCheck.

MIRA cung cấp sẵn:

```text
Full latent state
       ↓
remove one necessary fact
       ↓
Underdetermined Agent-A view
```

Ta tạo paired benchmark:

### UNDERSPECIFIED

Dùng trực tiếp Agent-A view:

\[
P^{-}.
\]

Đề không chứa missing fact.

Expected:

```text
ABSTAIN / REQUEST INFORMATION.
```

### OMISSION

Tạo:

\[
P^{+}
\]

bằng cách đưa canonical missing fact trở lại text.

Nhưng vẫn cho system cùng under-constrained formalization:

\[
F^{-}.
\]

Expected:

```text
REPAIR.
```

Vậy có:

\[
(P^+,F^-)
\]

và:

\[
(P^-,F^-).
\]

Đây gần như đúng experiment TargetCheck cần.

MIRA còn có các family như linear systems, CRT, geometry coordinates, graph path sums, matrix completion, recurrence, interpolation, circuits, Markov chains...

Không cần dùng toàn bộ 22 family.

Prototype chọn khoảng:

\[
6-10
\]

family tương thích tốt với solver fragment của mình.

---

# 17. Dataset size thực tế

Không nên chạy 2,310 × tất cả baselines × 3 models ngay.

Thiết kế hiệu quả hơn:

### Pilot

Khoảng:

\[
60-100\text{ pairs}
\]

chỉ GPT-OSS 20B.

Mục đích là quyết định:

> idea có tín hiệu hay không?

### Main controlled benchmark

Khoảng:

\[
300-500\text{ pairs}.
\]

Mỗi pair có:

- OMISSION;
- UNDERSPECIFIED.

Tổng:

\[
600-1000
\]

evaluation cases.

Stratify theo:

- problem family;
- difficulty.

### Full benchmark

Nếu thời gian/cloud credit còn:

chạy strongest baseline vs TargetCheck trên subset lớn hơn hoặc toàn bộ compatible MIRA instances.

---

# 18. Controlled formalization phải được tạo thế nào?

Không dùng LLM để tạo corrupted formalization trong experiment chính.

Ta cần biết chính xác error.

Giả sử gold formalization:

\[
F^*
=
\{c_1,\ldots,c_k,c^*\}.
\]

Trong đó \(c^*\) là canonical required fact.

Tạo:

\[
F^{-}
=
F^*\setminus\{c^*\}.
\]

Chỉ giữ sample nếu solver xác nhận:

\[
SAT(F^{-})
\]

và:

\[
SAT(
F^{-}_1
\land
F^{-}_2
\land
q_1\neq q_2
).
\]

Đồng thời gold phải target-determinate:

\[
UNSAT(
F^*_1
\land
F^*_2
\land
q_1\neq q_2
).
\]

Như vậy ta biết chắc:

> constraint vừa xóa thực sự là target-critical.

Đây là điểm methodology rất mạnh.

---

# 19. Tại sao controlled study chưa đủ?

Vì reviewer sẽ nói:

> “Các bạn chủ động xóa đúng một constraint. LLM ngoài đời có mắc lỗi kiểu này không?”

Đúng.

Do đó cần experiment thứ hai.

---

# 20. Experiment 2 — Natural formalization errors

Cho model nhận complete mathematical problem.

Model tự sinh Structured SymCode:

\[
P\rightarrow F.
\]

Không inject lỗi.

Sau đó chạy execution.

Thu các trường hợp:

```text
program executes
```

nhưng:

```text
final answer wrong
```

hoặc formalization không faithful.

Phân loại lỗi:

| Error | Ý nghĩa |
|---|---|
| Missing constraint | bỏ thông tin cần thiết |
| Wrong constraint | dịch quan hệ sai |
| Extra constraint | tự thêm assumption |
| Wrong domain | Int/Real/non-negative sai |
| Wrong target | hỏi \(x\) nhưng encode target khác |
| Computational | formalization đúng nhưng solve/code sai |
| Other | còn lại |

TargetCheck **không cần giải tất cả categories**.

Primary natural-error evaluation chỉ hỏi:

> Trong các executable under-constrained errors, TargetCheck phát hiện/sửa được bao nhiêu?

Điều này giữ claim sạch.

---

# 21. Có cần MATH-500 không?

Có, nhưng không nên biến MATH-500 thành benchmark chính của TargetCheck.

TargetCheck không phù hợp cho mọi loại MATH-500.

Ví dụ:

\[
\int_0^1x^2dx
\]

không có failure mode “missing constraint” giống word problem.

Vì vậy MATH-500 nên là **regression/general math evaluation**.

So sánh:

```text
Original SymCode
Structured SymCode
TargetCheck
```

và xem:

- answer accuracy;
- execution rate;
- verifier coverage;
- false repair rate;
- cost.

Mục tiêu:

> TargetCheck không làm hỏng reasoning chung.

Primary scientific evidence vẫn đến từ target-sensitive constraint problems.

Nếu còn thời gian mới thêm OlympiadBench.

---

# 22. Experiment 3 — MIRA interactive setting

MIRA còn cho một experiment rất hợp AAMAS.

Khi TargetCheck tìm:

\[
m_1,m_2,
\qquad
q(m_1)\neq q(m_2)
\]

nhưng source không chứa constraint để repair:

thay vì chỉ:

```text
ABSTAIN
```

nếu môi trường cho phép hỏi information holder thì agent có thể:

```text
REQUEST_INFORMATION
```

Ví dụ:

> “What is the value of the missing initial condition \(a_1\)?”

MIRA đã có Agent B để trả canonical missing fact.

Pipeline:

```text
ambiguity
   ↓
no source-grounded repair
   ↓
request missing information
   ↓
receive canonical fact
   ↓
add constraint
   ↓
TargetCheck again
   ↓
answer
```

Đây nên là secondary experiment nếu còn thời gian.

Nó làm AAMAS fit mạnh hơn mà không biến project thành logical reasoning hay multi-agent reasoning paper.

Core vẫn là **mathematical reasoning**.

---

# 23. Baselines

Controlled experiment nên có ít nhất:

| Method | Feedback cho repair model |
|---|---|
| Self-Review | Problem + current formalization |
| NonUnique | thêm “target is not uniquely determined” |
| Random Models | thêm hai feasible solutions bất kỳ |
| Target Witness | thêm hai solutions có target khác nhau |
| **TargetCheck** | target witnesses + grounded repair + explicit abstention |

Đây là ablation cực quan trọng.

## Self-Review

Kiểm tra xem đơn giản đọc lại đề có đủ không.

## NonUnique

Isolate value của solver verdict:

```text
The target is not uniquely determined.
```

## Random Models

Isolate value của việc cho concrete models.

Ví dụ:

```text
x=6,y=4,z=1

x=6,y=4,z=5
```

nhưng target đều:

\[
x=6.
\]

## Target Witness

Cố tình chọn:

\[
q(m_1)\neq q(m_2).
\]

Nếu Target Witness > Random Models:

> không phải chỉ vì model được xem thêm examples.

Nếu Target Witness > NonUnique:

> concrete target-specific counterexamples thực sự có giá trị.

## Full TargetCheck

Thêm:

- evidence requirement;
- explicit `ABSTAIN`;
- solver validation;
- iterative re-check.

---

# 24. End-to-end baselines

Ở experiment end-to-end:

| Method | Description |
|---|---|
| CoT | direct mathematical reasoning |
| SymCode | executable code baseline |
| Structured SymCode | cùng ModelSpec nhưng không TargetCheck |
| Structured SymCode + Self-Refine | generic semantic re-read |
| **TargetCheck** | proposed method |

`Structured SymCode` đặc biệt quan trọng.

Nếu không có baseline này, reviewer có thể nói:

> improvement đến từ structured representation chứ không phải TargetCheck.

---

# 25. Metrics chính

## Repair Success Rate

Trên omission cases:

\[
RSR=
\frac{
\#\text{correct repairs}
}{
\#\text{omission cases}
}.
\]

Correct repair nghĩa là candidate constraint semantically equivalent với gold missing fact và final target đúng.

---

## Correct Abstention Rate

Trên genuinely underspecified cases:

\[
CAR=
\frac{
\#\text{correct abstentions}
}{
\#\text{underspecified cases}
}.
\]

---

## Over-Repair Rate

Metric rất quan trọng:

\[
ORR=
P(
\text{system adds a constraint}
\mid
\text{problem genuinely underspecified}
).
\]

Lower better.

Đây gần như metric headline của paper.

---

## Under-Repair Rate

\[
URR=
P(
\text{system abstains}
\mid
\text{formalization omitted source information}
).
\]

Lower better.

---

## Final Decision Accuracy

Một output được tính đúng nếu:

### Omission case

system repair và trả correct answer.

### Underspecified case

system trả:

```text
UNDERSPECIFIED
```

hoặc request information đúng trong interactive experiment.

\[
FDA=
\frac{
\#\text{correct final decisions}
}{
N
}.
\]

Đây có thể là metric chính tổng hợp.

---

# 26. Metrics phụ

Báo thêm:

\[
\text{Target Determinacy Restoration Rate}
\]

\[
\text{Unsupported Constraint Rate}
\]

\[
\text{Solver UNKNOWN Rate}
\]

\[
\text{Verification Coverage}
\]

\[
\text{LLM Calls / Problem}
\]

\[
\text{Input Tokens}
\]

\[
\text{Output Tokens}
\]

\[
\text{Latency}
\]

\[
\text{Estimated Cost}.
\]

Không cần invent một weighted score kỳ lạ.

Các metrics riêng rẽ dễ defend hơn.

---

# 27. Statistical analysis

Vì cùng problem được chạy qua nhiều methods nên experiment mang tính paired.

Dùng:

### Bootstrap confidence intervals

95% CI cho:

- RSR;
- CAR;
- FDA;
- ORR.

### McNemar test

Cho pairwise binary comparison:

```text
TargetCheck vs NonUnique
TargetWitness vs RandomPair
TargetCheck vs Self-Review
```

### Macro + Micro

MIRA có số examples mỗi family khác nhau.

Nên báo:

```text
Micro average
Macro average over mathematical families
```

để family lớn không thống trị kết quả.

---

# 28. Ba model nên dùng

## GPT-OSS 20B

Dùng làm primary development model.

Ưu điểm:

- rẻ nhất;
- nhanh hơn;
- open-weight;
- support structured outputs/reasoning;
- rất phù hợp để pilot.

Ollama Cloud hiện hỗ trợ `gpt-oss:20b-cloud`; giá niêm yết hiện là $0.07/1M input tokens và $0.30/1M output tokens.

## GPT-OSS 120B

Strong-model condition.

Nếu TargetCheck chỉ giúp 20B mà không giúp 120B thì story sẽ khác:

> verifier có ích chủ yếu với weaker formalizers.

Nếu vẫn giúp 120B:

> stronger evidence rằng failure không biến mất chỉ nhờ scaling.

Ollama hiện hỗ trợ `gpt-oss:120b-cloud`, giá $0.15 input và $0.60 output trên 1M tokens.

## Gemma 4 31B

Cực kỳ có ích vì nó tạo **cross-family generalization**.

Nếu chỉ:

```text
GPT-OSS 20B
GPT-OSS 120B
```

reviewer có thể nói effect chỉ thuộc một model family.

Thêm Gemma:

\[
\text{OpenAI family}
\]

vs:

\[
\text{Google family}.
\]

Ollama hiện có chính thức `gemma4:31b-cloud`; model page ghi 31B, 256K context và cloud endpoint.

---

# 29. Không cần thuê GPU

Đây là project rất hợp với constraint hiện tại.

Computation nặng nhất của mình không phải neural training mà là:

```text
cloud LLM inference
+
local symbolic solving.
```

Local machine chỉ chạy:

- Python;
- SymPy;
- Z3;
- evaluation scripts;
- dataset generation;
- statistics.

Không có:

- fine-tuning;
- backprop;
- GPU training;
- model hosting.

Ollama Cloud chạy models trên cloud nên không cần GPU local.

Nhưng lưu ý:

> **Ollama Free hiện không phải unlimited cloud inference.**

Free tier cung cấp một lượng starter usage; cloud dùng token-based pricing.

Tin tốt là các models bạn chọn đều rất rẻ theo token.

Với experiment được thiết kế gọn, chi phí có khả năng vẫn ở mức thấp; đừng vì “free” mà generate reasoning dài vô hạn.

---

# 30. Model configuration

Không nên dùng config tùy tiện.

## GPT-OSS

OpenAI hiện khuyến nghị:

\[
temperature=1.0,
\qquad
top_p=1.0.
\]



Chọn:

```text
reasoning_effort = medium
```

làm default.

Không thay reasoning effort giữa các methods.

Có thể làm sensitivity:

```text
20B-medium
20B-high
```

trên một subset nhỏ nếu còn thời gian.

## Gemma 4

Ollama model page khuyến nghị:

```text
temperature = 1.0
top_p = 0.95
top_k = 64
thinking = enabled
```



Không cần ép tất cả model dùng cùng sampling parameters.

Quan trọng hơn là:

> trong cùng một model, mọi methods dùng cùng decoding configuration.

---

# 31. Reproducibility

Mỗi run lưu:

```json
{
  "problem_id": "...",
  "model": "gpt-oss:20b-cloud",
  "ollama_version": "...",
  "run_date": "...",
  "prompt_hash": "...",
  "method": "targetcheck",
  "seed": 42,
  "temperature": 1.0,
  "reasoning_effort": "medium",
  "initial_formalization": {},
  "solver_status": "...",
  "witness_1": {},
  "witness_2": {},
  "repair": {},
  "final_formalization": {},
  "final_answer": "...",
  "tokens": {}
}
```

Raw outputs cũng lưu.

Không đưa reasoning trace của previous turn lại vào history.

Chỉ truyền structured final output cần thiết.

Điều này vừa rẻ hơn vừa dễ reproduce.

---

# 32. Prompt budget fairness

Tất cả repair methods phải có cùng:

\[
K_{\max}=2
\]

repair attempts.

Không được:

```text
TargetCheck: 5 retries
Self-Review: 1 retry.
```

Nếu không reviewer sẽ bắt ngay.

Cũng nên cap output:

```text
JSON only
short justification
no long derivation
```

để token cost công bằng.

---

# 33. Pilot — thí nghiệm quyết định sống/chết của idea

Đừng code full project ngay.

Chạy khoảng:

\[
80\text{ pairs}
\]

trên GPT-OSS 20B.

Methods:

```text
Self-Review
NonUnique
TargetWitness
TargetCheck
```

Hai metrics cần nhìn ngay:

\[
RSR
\]

và:

\[
ORR.
\]

Ví dụ result rất đẹp:

| Method | Repair ↑ | Over-repair ↓ |
|---|---:|---:|
| Self-Review | 58 | 31 |
| NonUnique | 64 | 26 |
| TargetWitness | 76 | 22 |
| TargetCheck | **80** | **9** |

Nếu ra gần kiểu này:

> tiếp tục ngay.

Nếu:

| Method | Repair |
|---|---:|
| NonUnique | 72 |
| TargetWitness | 73 |

thì witness pair gần như không thêm giá trị.

Lúc đó novelty method yếu đi đáng kể.

---

# 34. Go / No-Go criterion

Mình sẽ đặt practical threshold trước khi đốt thời gian.

### GO mạnh

Nếu TargetWitness hơn `NonUnique`:

\[
\ge 5
\]

percentage points trên repair/final decision accuracy,

và TargetCheck giảm over-repair:

\[
\ge 10
\]

points so với generic repair,

đồng thời không làm Repair Success giảm mạnh.

### GO nhưng cần cải thiện

Witness gain:

\[
3-5
\]

points,

nhưng grounded abstention giảm hallucination rất rõ.

Lúc này story paper chuyển nhiều hơn sang:

> repair-vs-abstain.

### NO-GO

Nếu:

\[
TargetWitness\approx NonUnique
\]

và:

\[
TargetCheck
\]

không giảm unsupported repair đáng kể.

Khi đó không nên cố viết paper chỉ vì đã code.

---

# 35. Main hypotheses

## H1

\[
\text{TargetWitness}
>
\text{NonUnique}
\]

trên omitted-constraint repair.

Interpretation:

> concrete target-directed counterexamples có information value vượt quá binary verifier feedback.

## H2

\[
\text{TargetWitness}
>
\text{RandomPair}.
\]

Interpretation:

> target-directed witness selection quan trọng, không phải chỉ việc cho thêm concrete models.

## H3

\[
ORR(\text{TargetCheck})
<
ORR(\text{TargetWitness}).
\]

Interpretation:

> grounded repair + abstention ngăn LLM cưỡng ép answer.

## H4

Effect tồn tại trên ít nhất hai model families.

## H5

Trên natural errors, TargetCheck sửa một phần executable under-formalizations mà original SymCode không phát hiện.

---

# 36. Natural error study nên rất thật

Đừng chỉ báo final accuracy.

Cho một bảng kiểu:

| Failure | SymCode count | Detected by TargetCheck | Repaired |
|---|---:|---:|---:|
| Missing constraint | 42 | 35 | 29 |
| Wrong relation | 27 | 8 | 4 |
| Extra constraint | 18 | 1 | 0 |
| Wrong target | 9 | 2 | 1 |
| Computation | 31 | 0 | 0 |

Nếu TargetCheck chủ yếu xử lý missing constraints thì hoàn toàn okay.

Paper claim:

> TargetCheck is specialized rather than universal.

Reviewer thường thích một method biết rõ boundary của nó hơn method claim chữa mọi lỗi.

---

# 37. Failure cases cần phân tích

Ít nhất phân tích:

### Witness không đủ dễ hiểu

Hai solutions khác target nhưng khác quá nhiều variables khiến LLM khó localize missing fact.

### Multiple missing constraints

Một witness pair chưa đủ để tìm đúng một constraint.

### Implicit mathematical knowledge

Constraint đúng nhưng không có exact source span.

### Unsupported solver fragment

Transcendental/nonlinear expression.

### Hallucinated initial constraint

Target determinate nhưng formalization sai vì extra assumption.

### Incorrect repair semantics

LLM cite đúng sentence nhưng dịch sentence thành phương trình sai.

Cái cuối đặc biệt quan trọng:

> source citation không chứng minh semantic translation đúng.

Phải nói rõ.

---

# 38. Một enhancement có thể làm nếu pilot tốt

Thay vì feed raw witness pair:

```text
m1
m2
```

cho LLM trực tiếp, thêm **sentence localization**.

Problem tách thành:

```text
S1
S2
...
Sn
```

LLM đối chiếu mỗi sentence với witnesses:

```text
supported by both
violated by witness 1
violated by witness 2
irrelevant
```

Ví dụ:

```text
S1: A+B=10
m1 ✓
m2 ✓

S2: A=B+2
m1 ✗
m2 ✓
```

Sau đó repair từ:

```text
S2.
```

Pipeline trở thành:

\[
\text{witness}
\rightarrow
\text{source discrepancy localization}
\rightarrow
\text{constraint repair}.
\]

Method lúc này technical hơn đáng kể.

Nhưng chỉ thêm nếu basic TargetCheck pilot có tín hiệu.

---

# 39. Positioning với related work

## SymCode

SymCode:

\[
NL
\rightarrow
executable\ symbolic\ program
\rightarrow
execution
\rightarrow
answer.
\]

TargetCheck:

\[
NL
\rightarrow
formalization
\rightarrow
execution
\rightarrow
\boxed{target\ determinacy}
\rightarrow
repair/abstain.
\]

Paper story:

> SymCode makes computation executable; TargetCheck asks whether that executable representation actually contains enough information to justify the requested answer.



## ReLoop

ReLoop phát hiện feasibility-correctness gap bằng behavioral parameter perturbation trong optimization.

TargetCheck khác ở:

\[
\text{parameter perturbation}
\]

vs:

\[
\text{target-divergent model search}.
\]

Và TargetCheck explicitly phân biệt:

```text
formalization omission
```

với:

```text
source underspecification.
```

## SymDiag

SymDiag tập trung structured diagnosis của reasoning traces, step-level SAT/entailment và TranslationError vs ReasoningError.

TargetCheck không verify CoT step-by-step.

Nó hỏi một property hẹp:

\[
\text{Does the mathematical representation determine q?}
\]

## Minimal-core repair

Minimal unsat core xử lý phía:

\[
\text{over-constrained}
\rightarrow
UNSAT.
\]



TargetCheck xử lý phía đối xứng:

\[
\text{under-constrained}
\rightarrow
SAT + target ambiguity.
\]

Đây là positioning rất đẹp:

\[
\begin{array}{ccc}
\text{Overconstraint} &&
\text{Underconstraint}\\
UNSAT &&
SAT+\text{target ambiguity}\\
\text{Unsat core} &&
\text{Divergent witness pair}
\end{array}
\]

## MIRA-Math

MIRA-Math tập trung information acquisition khi mathematical view thiếu đúng một fact.

TargetCheck tập trung:

> symbolic verification signal quyết định khi nào representation cần repair, khi nào source thực sự không đủ.

MIRA trở thành benchmark rất tốt cho TargetCheck chứ không giết novelty.

---

# 40. Contribution claims nên viết thế nào

Contribution 1:

> We formulate **target determinacy checking** for executable LLM-generated mathematical formalizations, verifying whether all models satisfying the current constraints agree on the queried quantity.

Không claim mathematical notion itself là mới.

Contribution nằm ở cách operationalize nó cho LLM mathematical reasoning.

Contribution 2:

> We introduce **target-divergent witness feedback**, where a symbolic solver constructs two feasible assignments that disagree on the requested target and feeds them back for localized repair.

Contribution 3:

> We introduce a **grounded repair-or-abstain protocol** that distinguishes omitted source-supported constraints from genuine mathematical underspecification.

Contribution 4:

> We evaluate the method using controlled paired instances, naturally occurring formalization errors, and multiple open model families.

Nếu dùng MIRA:

> We construct a paired evaluation from MIRA-Math's validated latent states and missing atomic facts.

Không nên claim MIRA dataset là của mình.

---

# 41. Paper title

Mình thích nhất:

> **TargetCheck: Target-Determinate Verification for Executable Mathematical Reasoning**

Alternative:

> **Beyond Executability: Target-Determinate Verification for Neurosymbolic Mathematical Reasoning**

Alternative mạnh về motivation:

> **Does the Program Justify the Answer? TargetCheck for Executable Mathematical Reasoning**

Mình chọn title #1 hoặc #2.

---

# 42. Paper abstract story

Abstract nên đi theo logic:

```text
LLM + symbolic solvers
        ↓
execution guarantees computation
        ↓
but not faithful / sufficient formalization
        ↓
silent underconstraint
        ↓
TargetCheck
        ↓
solver searches for target-divergent witnesses
        ↓
grounded repair or abstention
        ↓
paired + natural evaluation
```

Không mở abstract bằng AAMAS/multi-agent.

Không ép story thành logical reasoning.

Không nói “first” trừ khi literature search cuối cùng đủ chắc.

---

# 43. AAMAS RR fit

AAMAS 2027 RR ghi trực tiếp các topic:

- neurosymbolic approaches;
- reasoning and problem solving in agent-based systems;
- verification;
- autoformalization;
- automated reasoning;
- reasoning methods hỗ trợ trustworthiness và explainability.

TargetCheck có:

\[
LLM
+
symbolic representation
+
solver
+
verification
+
autonomous repair
+
abstention.
\]

Do đó fit RR tốt.

Nhưng phải frame là:

> **a reasoning/verification method for an autonomous mathematical problem-solving agent**

chứ không phải:

> “chúng tôi prompt GPT tốt hơn trên MATH-500.”

AAMAS RR cho cả single-agent systems, không bắt buộc multi-agent.

Không cần ép project thành MAS.

---

# 44. Điểm AAMAS có thể bắt

AAMAS sẽ hỏi:

> Agent đâu?

Câu trả lời architecture phải rõ:

```text
The agent autonomously:
1. represents the mathematical task;
2. invokes symbolic tools;
3. inspects solver-generated evidence;
4. revises its representation;
5. decides whether to answer or abstain/request information.
```

Đó là một closed-loop reasoning agent.

MIRA interactive experiment càng làm framing này tự nhiên hơn.

---

# 45. Experiment tables mình muốn có trong paper

## Table 1 — Main paired results

```text
Model × Method
Repair Success
Correct Abstention
Final Decision Accuracy
Over-Repair
```

Đây là table chính.

## Table 2 — Ablation

```text
SelfReview
+ NonUnique
+ RandomPair
+ TargetWitness
+ Grounding/Abstention
```

## Table 3 — Natural errors

```text
failure taxonomy
detection
repair
```

## Table 4 — Cost

```text
calls
tokens
latency
```

Nếu thiếu page:

Table 4 đưa supplement.

---

# 46. Figures

Figure quan trọng nhất:

```text
Problem
 ↓
Structured SymCode
 ↓
TargetCheck
 ↓
target-divergent witnesses
 ↓
Grounded Repair
 ↙            ↘
repair       abstain
```

Figure 2 có thể là visualization:

```text
same F
 /   \
P+   P-
 |    |
repair abstain
```

Nó giải thích paired experiment cực nhanh.

Không cần nhiều figure.

---

# 47. 8-page AAMAS layout

AAMAS Main Track tối đa 8 trang nội dung, references không giới hạn; paper double-blind và LaTeX bắt buộc.

Mình chia:

```text
1. Introduction                 ~1.0
2. Related Work                ~0.7
3. Problem Formulation         ~0.8
4. TargetCheck                 ~1.7
5. Experimental Setup          ~1.1
6. Results                     ~1.6
7. Analysis + Limitations      ~0.8
8. Conclusion                  ~0.3
```

Appendix/supplement:

- prompts;
- dataset construction;
- full tables;
- natural error examples;
- model configs;
- additional ablations;
- source code details.

---

# 48. Timeline từ 09/09 đến submission

AAMAS 2027 hiện yêu cầu OpenReview accounts của authors trước **17/09/2026**, abstract trước **01/10/2026**, full paper trước **08/10/2026**.

## 09–13/09

Implement:

```text
ModelSpec
Z3 compiler
target determinacy checker
witness extraction
```

Test bằng hand-written problems.

## 14–16/09

Tích hợp:

```text
GPT-OSS 20B cloud
repair prompt
grounding gate
```

Tạo 60–100 pilot pairs.

## 17–19/09

Chạy pilot.

Đây là decision point:

```text
GO / PIVOT.
```

Và nhớ tất cả authors phải có OpenReview account trước 17/09.

## 20–24/09

Nếu GO:

- build MIRA-derived benchmark;
- implement baselines;
- run 20B full;
- bắt đầu natural error study.

## 25–29/09

Run:

```text
GPT-OSS 120B
Gemma 4 31B
```

Làm statistics.

Freeze main result tables.

## 30/09

Paper story phải gần như cố định.

## 01/10

Submit abstract.

## 02–05/10

Viết/finalize:

```text
Method
Experiments
Results
Related Work
```

## 06–07/10

- polish;
- double-blind check;
- citations;
- supplementary;
- reproducibility check.

## 08/10

Submit.

---

# 49. AAMAS AI-use policy phải lưu ý

Cái này liên quan trực tiếp tới project.

AAMAS 2027 cho phép dùng AI tools cho code/scripts, polishing và experiments. Nhưng nếu AI-assisted tools được dùng trong **hypothesis creation, methodology hoặc experimental design**, paper/supplement phải cung cấp chi tiết về tool/version và prompts liên quan.

Vì quá trình thiết kế TargetCheck hiện có AI assistance, mình sẽ không né chuyện này.

Trong supplementary nên có ngắn gọn:

```text
AI-assisted research disclosure
- system/tool used;
- model/version where available;
- role in brainstorming/methodology;
- representative prompts;
- authors independently verified the method,
  implementation, literature and experimental conclusions.
```

Đừng để đây thành lý do desk reject.

---

# 50. Repo structure mình đề xuất

```text
targetcheck/
│
├── data/
│   ├── mira_raw/
│   ├── paired/
│   └── natural_errors/
│
├── targetcheck/
│   ├── modelspec.py
│   ├── compiler_sympy.py
│   ├── compiler_z3.py
│   ├── determinacy.py
│   ├── witnesses.py
│   ├── grounding.py
│   ├── repair.py
│   └── pipeline.py
│
├── baselines/
│   ├── self_review.py
│   ├── nonunique.py
│   ├── random_pair.py
│   └── target_witness.py
│
├── providers/
│   └── ollama_cloud.py
│
├── evaluation/
│   ├── metrics.py
│   ├── statistics.py
│   ├── error_taxonomy.py
│   └── cost.py
│
├── scripts/
│   ├── build_paired_mira.py
│   ├── run_pilot.py
│   ├── run_main.py
│   └── analyze.py
│
└── configs/
    ├── gpt_oss_20b.yaml
    ├── gpt_oss_120b.yaml
    └── gemma4_31b.yaml
```

---

# 51. Minimum viable paper

Nếu thời gian bị dí sát, **đừng cố làm hết**.

Minimum publishable version:

```text
1. Structured SymCode
2. Target determinacy checker
3. target-divergent witnesses
4. grounded repair/abstain
5. paired MIRA-derived benchmark
6. 3 models
7. 4 baselines
8. small natural-error validation
```

Bỏ:

- OlympiadBench;
- multiple repair strategies;
- complicated nonlinear math;
- training;
- fine-tuning;
- MUC;
- multi-agent extensions.

Scope nhỏ nhưng clean quan trọng hơn.

---

# 52. Strong version nếu mọi thứ chạy sớm

Nếu pilot xong rất nhanh, thêm:

### Two-sided verification

```text
UNSAT
 ↓
minimal unsat core
 ↓
overconstraint repair
```

và:

```text
SAT + target ambiguity
 ↓
target-divergent witnesses
 ↓
underconstraint repair
```

Nhưng **không nên bắt đầu bằng version này**.

TargetCheck một phía đã đủ làm research question.

---

# 53. Biggest novelty risk

Reviewer có thể nói:

> “This is simply checking whether multiple solver solutions give different answers.”

Phản hồi của paper phải nằm trong experiments:

Không claim solver formula đó là innovation lớn.

Innovation phải được chứng minh bằng:

\[
\text{TargetWitness}
>
\text{NonUnique}
\]

và:

\[
\text{TargetWitness}
>
\text{RandomPair}.
\]

Nếu hai inequality này không xảy ra empirically, method contribution yếu.

---

# 54. Biggest soundness risk

Reviewer:

> “UNSAT on the duplicated model only establishes uniqueness under the generated formalization, not correctness w.r.t. the natural-language problem.”

Phải đồng ý.

Không né.

Paper viết:

> TargetCheck certifies target determinacy under the current formalization; it is not a complete semantic-equivalence checker.

Sau đó giải thích grounding/provenance giảm một failure mode nhưng không cung cấp full semantic proof.

Đây là stance khoa học đúng.

---

# 55. Biggest experimental risk

Reviewer:

> “Results only work because authors manually deleted constraints.”

Giải bằng:

1. MIRA externally defined missing facts;
2. paired controlled experiment;
3. natural LLM formalization errors;
4. multiple model families.

Nếu đủ bốn cái thì critique này yếu đi rất nhiều.

---

# 56. Biggest AAMAS risk

Không phải technical.

Là reviewer nghĩ:

> “Đây chỉ là NLP mathematical reasoning.”

Vì vậy introduction/conclusion phải nói rõ:

> TargetCheck is a verification-and-repair mechanism for a single autonomous reasoning agent that constructs and revises symbolic task representations.

Và architecture thật sự phải autonomous.

Không fake multi-agent terminology.

RR 2027 explicit có autoformalization, verification và neurosymbolic reasoning nên submission này có đường fit tương đối tốt.

---

# 57. Tự chấm paper ở trạng thái Ý TƯỞNG HIỆN TẠI

Nếu submit chỉ bằng idea hiện tại, chưa experiments:

| Criterion | Score |
|---|---:|
| Problem importance | 8/10 |
| Novelty | 6.5/10 |
| Method clarity | 7.5/10 |
| Technical depth | 6.5/10 |
| Evidence | 2/10 |
| AAMAS RR fit | 7.5/10 |
| Overall | **6.3/10** |

Tức:

> promising nhưng đương nhiên chưa submit được.

---

# 58. Nếu thực nghiệm ra đúng signal mình kỳ vọng

Giả sử:

- TargetWitness thắng NonUnique rõ;
- TargetWitness thắng RandomPair;
- TargetCheck giảm over-repair mạnh;
- effect có trên 20B, 120B và Gemma;
- natural-error study xác nhận SymCode thực sự mắc executable under-formalization;
- cost/reproducibility tốt.

Mình sẽ chấm:

| Criterion | Score |
|---|---:|
| Originality | 7.5/10 |
| Significance | 7.5/10 |
| Technical soundness | 8/10 |
| Experimental design | 8.5/10 |
| Reproducibility | 9/10 |
| Clarity | 8/10 |
| RR relevance | 8/10 |
| Overall | **8.0/10** |

Reviewer-style:

\[
\boxed{\text{Weak Accept → Accept}}
\]

Mình sẽ xem đây là paper **có cửa Proceedings AAMAS thật**, không phải nộp cho vui.

---

# 59. Ước lượng khả năng accept

Đây là đánh giá chủ quan của mình, **không phải acceptance-rate statistics của AAMAS**.

### Scenario A — Strong result

TargetCheck thắng strong baselines ≥5–10 points, giảm hallucinated repair rõ, natural errors support story, ≥2 model families.

Mình sẽ ước lượng:

```text
AAMAS Proceedings:      ~50–65%
Proceedings or Findings: ~70–80%
```

AAMAS 2027 lần đầu có Findings; submissions không vào Proceedings sẽ tự động được xét Findings nếu authors không opt out.

### Scenario B — Controlled benchmark tốt nhưng natural errors yếu

```text
Proceedings: ~30–45%
```

Khả năng Findings vẫn tương đối ổn nếu methodology sound.

### Scenario C — TargetWitness ≈ NonUnique

Novelty giảm mạnh.

```text
Proceedings: <25%
```

Mình sẽ không submit current story mà pivot.

### Scenario D — chỉ thêm verifier rồi accuracy +1–2%

Khả năng reject cao.

Vì reviewer sẽ coi là incremental SymCode extension.

---

# 60. Điều mình muốn nhìn thấy nhất trong kết quả

Không phải:

> “TargetCheck tăng MATH accuracy 2%.”

Mà là table kiểu:

| | Omission: correct repair ↑ | Underspecified: correct abstain ↑ |
|---|---:|---:|
| Self-Review | 61 | 58 |
| NonUnique | 67 | 62 |
| RandomPair | 68 | 63 |
| TargetWitness | **79** | 61 |
| **TargetCheck** | **81** | **88** |

Table này kể toàn bộ story:

**Witness giúp biết sửa cái gì.**

**Grounding + abstention giúp biết khi nào không nên sửa.**

Nếu ra được pattern này trên cả:

```text
GPT-OSS 20B
GPT-OSS 120B
Gemma 4 31B
```

thì mình sẽ khá tự tin viết AAMAS.

---

# 61. Paper thesis cuối cùng

Paper không phải:

> “SymCode nhưng accuracy cao hơn.”

Paper cũng không phải:

> “Một semantic verifier tổng quát.”

Paper là:

\[
\boxed{
\text{Executable mathematical reasoning needs
a notion of whether the current representation
actually determines the requested answer.}
}
\]

TargetCheck operationalizes điều đó bằng:

\[
\boxed{
F_1\land F_2\land q_1\neq q_2
}
\]

và khi ambiguity tồn tại:

\[
\boxed{
\text{target-divergent witnesses}
\rightarrow
\text{grounded repair or abstention}.
}
\]

Story đầy đủ:

```text
SymCode asks:
"Can I execute this mathematical representation?"

TargetCheck additionally asks:
"Does this representation justify the answer
that I am about to return?"
```

Đó là câu mình sẽ dùng làm xương sống cho toàn paper.

---

# 62. Quyết định cuối

**Mình nghĩ nên làm hướng này.**

Đặc biệt vì:

- bạn đã có nền SymCode;
- không cần training;
- không cần thuê GPU;
- solver local rất nhẹ;
- MIRA-Math đã cho mình benchmark missing-information khá đẹp;
- experimental hypothesis rất falsifiable;
- có kill criterion sớm;
- fit trực tiếp với `neurosymbolic approaches`, `verification`, `autoformalization` trong AAMAS RR.

Việc đầu tiên không phải chạy 120B.

Việc đầu tiên là:

\[
\boxed{
\text{80 paired examples}
+
\text{GPT-OSS 20B}
+
\text{NonUnique vs TargetWitness vs TargetCheck}.
}
\]

Nếu pilot chứng minh witness feedback thực sự tốt hơn generic non-unique feedback và grounding thực sự giảm over-repair, lúc đó mới scale sang 120B + Gemma và bắt đầu viết paper.

Nếu pilot không cho tín hiệu, bỏ/pivot sớm.

Đó là cách an toàn nhất để biến một tháng còn lại thành một submission có chất lượng.