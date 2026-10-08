# ALG514 30B schema run audit

Source: `results/alg514_30b_schema_20261003_215420.jsonl`

Direct 494/499 (99.00%); ModelSpec/Z3 492/499 (98.60%). No API exclusions or compiler errors.
Both correct: 490. Direct-only correct: 1315, 3623, 3648, 6334. ModelSpec-only correct: 6004, 6525. Both wrong: 2196, 2559, 6072.

32 schema corrections succeeded (31 single-target unordered flags, 1 malformed JSON). 17 cases entered grounded repair, 23 proposals, 15 accepted; 14 accepted cases match gold.

Important: 2196 is not merely a gold issue in this run; the formalization also omits the 3-hour multiplier. 6334 has an ambiguous wording interpretation. 6072 is a threshold/minimum count problem outside the stated evaluated fragment, and the accepted repair pins a computed target. Do not silently change data or gold based on these errors.

## alg514/1315

The sum of 2 numbers is 27 . 0.5 of the first number plus 0.3333333 of the second number is 11 . Find the smaller and the larger number .

Gold: `[12.0, 15.0]`. Direct: `['12', '15']` (correct=True).
ModelSpec: `NO_ADMISSIBLE_REPAIR_FOUND`, `[]`.
Khai báo smaller/larger nhưng không có ràng buộc nào liên kết chúng với a,b. a,b đã xác định, targets vẫn tự do. Repair a<b bị reject vì đã suy ra; lần thứ hai bị reject vì span không khớp chính xác (the sum khác The sum). Cần binding target theo thứ tự nhỏ/lớn được hỏi.

```json
{
  "status": "SUPPORTED",
  "variables": {
    "a": "Real",
    "b": "Real",
    "smaller": "Real",
    "larger": "Real"
  },
  "constraints": [
    "a + b == 27",
    "0.5*a + 0.3333333*b == 11"
  ],
  "targets": [
    "smaller",
    "larger"
  ],
  "unordered_targets": false
}
```

Repair trace:
```json
[
  {
    "attempt": 1,
    "raw": "{\n  \"decision\": \"add-constraint\",\n  \"source_span\": \"the smaller and the larger number\",\n  \"constraint\": \"a < b\"\n}",
    "proposal": {
      "decision": "add-constraint",
      "source_span": "the smaller and the larger number",
      "constraint": "a < b"
    },
    "result": "REJECTED",
    "reason": "ValueError: Addition is redundant or novelty is inconclusive"
  },
  {
    "attempt": 2,
    "raw": "{\"decision\":\"add-constraint\",\"source_span\":\"the sum of 2 numbers is 27 . 0.5 of the first number plus 0.3333333 of the second number is 11 . Find the smaller and the larger number\",\"constraint\":\"smaller + larger == 27 and 0.5*smaller + 0.3333333*larger == 11\"}",
    "proposal": {
      "decision": "add-constraint",
      "source_span": "the sum of 2 numbers is 27 . 0.5 of the first number plus 0.3333333 of the second number is 11 . Find the smaller and the larger number",
      "constraint": "smaller + larger == 27 and 0.5*smaller + 0.3333333*larger == 11"
    },
    "result": "REJECTED",
    "reason": "ValueError: Supporting span must occur verbatim in the source"
  }
]
```

## alg514/2196

A freight train and an express train leave towns 390 kilometers apart , traveling toward one another . The freight train travels 30 kilometers per hour slower than the express train . They pass one another 3 hours later . How fast is the freight train , in miles per hour ? How fast is the express train ?

Gold: `[50.0, 80.0]`. Direct: `['31.07', '49.71']` (correct=False).
ModelSpec: `DETERMINATE`, `['5592339/50000', '13048791/100000']`.
Sai formalization: viết freight_k+express_k=390 thay vì 3*(freight_k+express_k)=390. Trả 111.84678,130.48791 mph. Sửa hệ số thời gian cho 31.06855,49.70968 mph, vẫn không khớp gold 50,80 km/h; gold và đơn vị câu hỏi cũng mâu thuẫn. Direct trả 31.07,49.71 mph phù hợp đơn vị đề.

```json
{
  "status": "SUPPORTED",
  "variables": {
    "freight_k": "Real",
    "express_k": "Real",
    "freight_mph": "Real",
    "express_mph": "Real"
  },
  "constraints": [
    "freight_k + express_k == 390",
    "express_k - freight_k == 30",
    "freight_mph == freight_k * 0.621371",
    "express_mph == express_k * 0.621371"
  ],
  "targets": [
    "freight_mph",
    "express_mph"
  ],
  "unordered_targets": false
}
```

## alg514/2559

The total number of Democrats and Republicans in the House of Representatives was 434 . There were 30 more Republicans then Democrats . How many Democrats and Republicans were there in the Senate ?

Gold: `[202.0, 232.0]`. Direct: `['unknown', 'unknown']` (correct=False).
ModelSpec: `NOT_SUPPORTED`, `[]`.
Dữ kiện House of Representatives nhưng câu hỏi Senate. Gold 202,232 là nghiệm cho House. ModelSpec NOT_SUPPORTED và direct unknown; không thể suy ra Senate từ các dữ kiện này.

```json
{
  "status": "NOT_SUPPORTED",
  "variables": {},
  "constraints": [],
  "targets": []
}
```

## alg514/3623

For Monday morning 's staff meeting , Jim bought 2 bags of bagels and 3 packages of cream cheese and paid 12.00 dollars . For Friday 's meeting , he bought 4 bags of bagels and 2 packages of cream cheese and paid 14.00 dollars . How much does a bag of bagels and a package of cream cheese cost , in dollars ?

Gold: `[2.25, 2.5]`. Direct: `['2.25', '2.5']` (correct=True).
ModelSpec: `DETERMINATE`, `['19/4']`.
Phương trình giá bagel/cream cheese đúng nhưng target a+b trả tổng 4.75. Gold yêu cầu hai giá riêng 2.25,2.50.

```json
{
  "status": "SUPPORTED",
  "variables": {
    "a": "Real",
    "b": "Real"
  },
  "constraints": [
    "2*a+3*b==12.0",
    "4*a+2*b==14.0"
  ],
  "targets": [
    "a+b"
  ],
  "unordered_targets": false
}
```

## alg514/3648

Find two numbers whose sum is 14 if one number is 3 times as large as the other number .

Gold: `[3.5, 10.5]`. Direct: `['21/2', '7/2']` (correct=True).
ModelSpec: `NO_ADMISSIBLE_REPAIR_FOUND`, `[]`.
Tổng 14 và một số gấp 3 số kia xác định cặp {3.5,10.5}. unordered_targets=false khiến hai hoán vị bị coi khác target. Repair abstain. Chỉ đổi metadata unordered_targets=true là determinate.

```json
{
  "status": "SUPPORTED",
  "variables": {
    "a": "Real",
    "b": "Real"
  },
  "constraints": [
    "a + b == 14",
    "(a == 3*b) or (b == 3*a)"
  ],
  "targets": [
    "a",
    "b"
  ],
  "unordered_targets": false
}
```

Repair trace:
```json
[
  {
    "attempt": 1,
    "raw": "{\"decision\":\"abstain\",\"source_span\":\"\",\"constraint\":\"\"}",
    "proposal": {
      "decision": "abstain",
      "source_span": "",
      "constraint": ""
    },
    "result": "ABSTAIN"
  }
]
```

## alg514/6072

Suppose you invest 1,500 dollars in equipment to put pictures on T-shirts . You buy each T-shirt for 3 dollars . After you have placed the pictures on a shirt , you sell it for 20 dollars . How many T-shirts must you sell to break even ?

Gold: `[88.23529]`. Direct: `['89']` (correct=False).
ModelSpec: `DETERMINATE`, `['89']`.
Spec Int n và 20*n >= 1500+3*n có nhiều nghiệm (n>=89), không xác định một target duy nhất. Repair đầu thêm hòa vốn chính xác bị INCONSISTENT; repair sau pin n=89 được gate chấp nhận. 89 là số nguyên tối thiểu để không lỗ, nhưng tối ưu/ngưỡng ngoài scope công bố; gate chỉ kiểm tra span có mặt và determinacy, không chứng minh ngữ nghĩa. Gold là điểm hòa vốn liên tục 88.23529. Cả hai flow trả 89 bị chấm sai.

```json
{
  "status": "SUPPORTED",
  "variables": {
    "n": "Int"
  },
  "constraints": [
    "20*n>=1500+3*n"
  ],
  "targets": [
    "n"
  ],
  "unordered_targets": false
}
```

Repair trace:
```json
[
  {
    "attempt": 1,
    "raw": "{\n  \"decision\": \"add-constraint\",\n  \"source_span\": \"invest 1,500 dollars in equipment to put pictures on T-shirts . You buy each T-shirt for 3 dollars . After you have placed the pictures on a shirt , you sell it for 20 dollars\",\n  \"constraint\": \"20*n == 1500 + 3*n\"\n}",
    "proposal": {
      "decision": "add-constraint",
      "source_span": "invest 1,500 dollars in equipment to put pictures on T-shirts . You buy each T-shirt for 3 dollars . After you have placed the pictures on a shirt , you sell it for 20 dollars",
      "constraint": "20*n == 1500 + 3*n"
    },
    "result": "REJECTED",
    "reason": "ValueError: Repair must restore determinacy; got INCONSISTENT"
  },
  {
    "attempt": 2,
    "raw": "{\n  \"decision\": \"add-constraint\",\n  \"source_span\": \"Suppose you invest 1,500 dollars in equipment to put pictures on T-shirts . You buy each T-shirt for 3 dollars . After you have placed the pictures on a shirt , you sell it for 20 dollars . How many T-shirts must you sell to break even ?\",\n  \"constraint\": \"n == 89\"\n}",
    "proposal": {
      "decision": "add-constraint",
      "source_span": "Suppose you invest 1,500 dollars in equipment to put pictures on T-shirts . You buy each T-shirt for 3 dollars . After you have placed the pictures on a shirt , you sell it for 20 dollars . How many T-shirts must you sell to break even ?",
      "constraint": "n == 89"
    },
    "result": "ACCEPTED"
  }
]
```

## alg514/6334

The Lakers scored 43 points on a combination of 20 two point baskets and three point baskets . How many shots of two point baskets and how many shots of three point baskets were made ?

Gold: `[17.0, 3.0]`. Direct: `['17', '3']` (correct=True).
ModelSpec: `DETERMINATE`, `['20', '1']`.
Spec hiểu 20 là số cú ném 2 điểm: a=20, 2a+3b=43 -> 20,1. Gold và direct hiểu tổng số cú ném là 20: a+b=20 -> 17,3. Câu combination of 20 two point baskets and three point baskets dễ gây nhập nhằng; cần adjudication source, không tự sửa theo gold.

```json
{
  "status": "SUPPORTED",
  "variables": {
    "a": "Int",
    "b": "Int"
  },
  "constraints": [
    "a == 20",
    "2*a + 3*b == 43"
  ],
  "targets": [
    "a",
    "b"
  ],
  "unordered_targets": false
}
```

## Cases won by ModelSpec

6004: Direct returns profit ratio 1/5; ModelSpec returns profit amount 11, matching gold.
6525: Direct returns 5.4,0.4 as requested to the nearest tenth; gold is unrounded 5.416068866571019,0.39454806312769. ModelSpec returns unrounded fractions, matching gold but omitting requested output rounding.

Original outputs, dataset and script unchanged; no inference run.
