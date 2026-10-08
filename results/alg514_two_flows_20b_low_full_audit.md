# ALG514: GPT-OSS 20B Direct vs ModelSpec → Z3

LLM -> ModelSpec -> Z3 baseline; no repair step. Existing run predates the current revised system prompt. Scoring is ALG514-compatible numeric subset matching, not ordered requested-answer evaluation.

Không chạy inference/API mới; giữ nguyên file kết quả gốc.

| Phạm vi | Cases | Direct | ModelSpec → Z3 |
|---|---:|---:|---:|
| all | 514 | 500/514 (97.28%) | 477/514 (92.80%) |
| exclude_minmax_threshold | 502 | 489/502 (97.41%) | 475/502 (94.62%) |
| also_exclude_resource_limit | 498 | 485/498 (97.39%) | 474/498 (95.18%) |

Paired: cả hai đúng 467; chỉ Direct đúng 33; chỉ ModelSpec đúng 10; cả hai sai 4.

37 case ModelSpec bị chấm sai: 10 min/max/ngưỡng; 3 giới hạn tài nguyên; 5 thiếu hoặc sai mô hình/target dẫn đến ambiguity; 7 syntax; 5 inconsistent; 5 determinate nhưng lệch gold; 2 NOT_SUPPORTED.

Bộ lọc hậu kiểm được áp dụng cho cả hai flow theo nội dung câu hỏi, gồm cả case đã đúng. Không xem là một kiểm định xác nhận độc lập.

Min/max/ngưỡng bị loại: 657, 1035, 1119, 2031, 3285, 3542, 5298, 5894, 6348, 6540, 6759, 6779.
Giới hạn tài nguyên bị loại thêm: 15, 2120, 6336, 6426.

- Post-hoc scope filters are descriptive, selected from problem meaning and applied identically to both flows, including correctly answered excluded cases.
- No observed solver arithmetic failure in this audit. Solver results refer to encoded constraints, not semantic faithfulness.
- All 7 ModelSpec ERROR records are syntax/compiler failures, not API timeouts.
- Offline operator-only normalization fixes final answer credit for 1 of 7 syntax cases; 5 remain ambiguous and 1 inconsistent.
- Direct failures include 4 two-answer strings wrongly joined by slash (920,1309,3246,5281).
- Gold mismatches include units (2196), conflicting direction (6853), House vs Senate (2559), and continuous count at break-even (6072). Direct 6525 follows requested rounding but is scored against unrounded gold.

## Từng case ModelSpec bị chấm sai

### alg514/15 — AMBIGUOUS (resource_limit)

Giữ pages <= 21 và words <= 48000 theo giới hạn trong đề; gold giả định dùng hết cả hai. Chưa có điều kiện cố định nghiệm.

Đề: John is writing an article . The article is limited to 48,000 words . He decides to use two types of font . Large font is 1,800 words per page , small font is 2,400 words per page . He is allowed 21 pages for this article . How many pages are in small font ? How many pages are in large font ?

Direct: ['17', '4'] — correct=True; Z3: []; gold: [17.0, 4.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "small": "Int",
    "large": "Int"
  },
  "constraints": [
    "small + large <= 21",
    "2400 * small + 1800 * large <= 48000",
    "small >= 0",
    "large >= 0"
  ],
  "targets": [
    "small",
    "large"
  ]
}
```

### alg514/155 — ERROR (syntax)

Dùng toán tử ngoài cú pháp Python được hỗ trợ. Chỉ sửa toán tử thì vẫn AMBIGUOUS do hoán đổi vai trò hai số.

Đề: A piece of rope 60 meters long is cut into two pieces so that the longest piece is twice as long as the shorter piece . How long are the two pieces ?

Direct: ['20', '40'] — correct=True; Z3: []; gold: [20.0, 40.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real",
    "y": "Real"
  },
  "constraints": [
    "x + y == 60",
    "(x >= y && x == 2*y) || (y >= x && y == 2*x)",
    "x >= 0",
    "y >= 0"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

Error: SyntaxError: invalid syntax (<unknown>, line 1)

### alg514/580 — INCONSISTENT (inconsistent)

Khai báo số phút là Int, nhưng 5 + 0.25*m == 12.02 đòi m = 28.08. Phải dùng Real cho thời gian.

Đề: For his long distance phone calls , John pays a 5 dollars monthly fee plus 25 cents per minute . Last month , John 's long distance bill was 12.02 dollars . For how many minutes was John billed ?

Direct: ['702/25'] — correct=True; Z3: []; gold: [28.08]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "m": "Int"
  },
  "constraints": [
    "5 + 0.25 * m == 12.02",
    "m >= 0"
  ],
  "targets": [
    "m"
  ]
}
```

### alg514/657 — AMBIGUOUS (minmax_threshold)

Giữ bất đẳng thức thời điểm mất liên lạc; cần tìm thời điểm đầu tiên, không phải giá trị duy nhất trên miền khả thi.

Đề: 2 teams of scientists leave a university at the same time in special vans to search for tornadoes . the 1st team travel east at 20 miles per hour and the 2nd team travels west at 30 miles per hour . their radios have a range of 125 miles . How much time will pass before the scientists lose radio contact ?

Direct: ['2.5'] — correct=True; Z3: []; gold: [2.5]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "t": "Real"
  },
  "constraints": [
    "50 * t >= 125",
    "t >= 0"
  ],
  "targets": [
    "t"
  ]
}
```

### alg514/1035 — AMBIGUOUS (minmax_threshold)

Lương tối thiểu dẫn đến miền doanh số >= 5000; cần mục tiêu tối thiểu.

Đề: Jordan 's salary is 1250 dollars a month plus a 5 % commission on all of his sales . What must the amount of his sales be , in dollars , for him to earn at least 1500 dollars each month ?

Direct: ['5000'] — correct=True; Z3: []; gold: [5000.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "s": "Real"
  },
  "constraints": [
    "1250 + 0.05 * s >= 1500",
    "s >= 0"
  ],
  "targets": [
    "s"
  ]
}
```

### alg514/1089 — DETERMINATE (determinate_wrong)

Dịch sai: cork + 2 == 2.10. Đúng là wine + cork == 2.10 và wine == cork + 2; cork = 0.05.

Đề: A bottle of wine with a cork cost 2.10 dollars . A bottle of wine without a cork costs 2.00 dollars more than the cork . What is the price of the cork ?

Direct: ['1/20'] — correct=True; Z3: ['1/10']; gold: [0.05, 2.05]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real"
  },
  "constraints": [
    "x + 2.00 == 2.10",
    "x >= 0"
  ],
  "targets": [
    "x"
  ]
}
```

### alg514/1119 — AMBIGUOUS (minmax_threshold)

Giới hạn ngân sách cho miles <= 200; cần tối đa hóa miles.

Đề: A car rents for 30 dollars per day plus 23 cents per mile . You are on a daily budget of 76 dollars . What mileage can you go and stay within your budget ?

Direct: ['200'] — correct=True; Z3: []; gold: [200.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real"
  },
  "constraints": [
    "30 + 0.23 * x <= 76",
    "x >= 0"
  ],
  "targets": [
    "x"
  ]
}
```

### alg514/1532 — DETERMINATE (determinate_wrong)

Dịch 36 less than twice theo 36 - 2*x; gold dùng 2*x - 36. Direct cũng trả 3; cần kiểm tra cách diễn đạt với gold.

Đề: The product of 10 and a number is the same as 36 less twice that same number . Find the number .

Direct: ['3'] — correct=False; Z3: ['3']; gold: [-4.5]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real"
  },
  "constraints": [
    "10 * x == 36 - 2 * x"
  ],
  "targets": [
    "x"
  ]
}
```

### alg514/2031 — AMBIGUOUS (minmax_threshold)

Giới hạn ngân sách cho miles <= 250; cần tối đa hóa miles.

Đề: A car rents for 30 dollars per day plus 18 cents per mile . You are on a budget of 75 dollars . What mileage would allow you to stay within your budget ?

Direct: ['250'] — correct=True; Z3: []; gold: [250.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real"
  },
  "constraints": [
    "30 + 0.18 * x <= 75",
    "x >= 0"
  ],
  "targets": [
    "x"
  ]
}
```

### alg514/2074 — INCONSISTENT (inconsistent)

Thêm cả x == 0.375*y + 4 và quan hệ đảo y == 0.375*x + 4. Đề chỉ cho một chiều.

Đề: Find two numbers whose sum is 147 and one is 4 greather than 0.375 of the other .

Direct: ['43', '104'] — correct=True; Z3: []; gold: [43.0, 104.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real",
    "y": "Real"
  },
  "constraints": [
    "x + y == 147",
    "x == 0.375 * y + 4",
    "y == 0.375 * x + 4",
    "x >= 0",
    "y >= 0"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

### alg514/2075 — INCONSISTENT (inconsistent)

Các quan hệ cho x=6,y=4 nhưng thêm x<=y để ép thứ tự, làm hệ vô nghiệm. Cần đổi thứ tự targets theo vai trò.

Đề: The sum of 2 numbers is 10 . 3 times one of them is more than 4 times the second by 2 . Find the smaller number . Find the larger number .

Direct: ['4', '6'] — correct=True; Z3: []; gold: [4.0, 6.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real",
    "y": "Real"
  },
  "constraints": [
    "x + y == 10",
    "3 * x == 4 * y + 2",
    "x >= 0",
    "y >= 0",
    "x <= y"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

### alg514/2120 — AMBIGUOUS (resource_limit)

Mô hình giữ hours <= 5800 và cost <= 12600 theo nguồn; gold dùng hai đẳng thức tiêu hết tài nguyên.

Đề: A manufacturer produces two models of the same toy , Model A and Model B. Model A takes 4 hours to produce and costs 8 dollars each . Model B takes 3 hours to produce and costs 7 dollars each . If the manufacturer allots a total of 5800 hours and 12,600 dollars for production each week , how many of each model will be produced ?

Direct: ['700', '1000'] — correct=True; Z3: []; gold: [700.0, 1000.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Int",
    "y": "Int"
  },
  "constraints": [
    "4 * x + 3 * y <= 5800",
    "8 * x + 7 * y <= 12600",
    "x >= 0",
    "y >= 0"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

### alg514/2196 — DETERMINATE (determinate_wrong)

Đề hỏi miles/hour, ModelSpec đổi từ km/hour ra mph; gold vẫn 50,80 km/hour. Direct cũng đổi đơn vị nên cả hai bị chấm sai.

Đề: A freight train and an express train leave towns 390 kilometers apart , traveling toward one another . The freight train travels 30 kilometers per hour slower than the express train . They pass one another 3 hours later . How fast is the freight train , in miles per hour ? How fast is the express train ?

Direct: ['31.06855', '49.70968'] — correct=False; Z3: ['621371/20000', '621371/12500']; gold: [50.0, 80.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "f": "Real",
    "e": "Real",
    "f_mph": "Real",
    "e_mph": "Real"
  },
  "constraints": [
    "f * 3 + e * 3 == 390",
    "e == f + 30",
    "f_mph == f * 0.621371",
    "e_mph == e * 0.621371",
    "f >= 0",
    "e >= 0"
  ],
  "targets": [
    "f_mph",
    "e_mph"
  ]
}
```

### alg514/2247 — DETERMINATE (determinate_wrong)

Dịch tổng 30 nickels and dimes thành n == 30; đúng là n+d == 30, n=12.

Đề: Sam has 30 nickels and dimes worth 2.40 dollars . How many nickels does he have ?

Direct: ['12'] — correct=True; Z3: ['30']; gold: [12.0, 18.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "n": "Int",
    "d": "Int"
  },
  "constraints": [
    "n == 30",
    "5 * n + 10 * d == 240",
    "n >= 0",
    "d >= 0"
  ],
  "targets": [
    "n"
  ]
}
```

### alg514/2559 — NOT_SUPPORTED (unsupported)

Nguồn đưa dữ kiện House nhưng hỏi Senate; model từ chối, gold giải House. Có bất nhất nguồn/gold.

Đề: The total number of Democrats and Republicans in the House of Representatives was 434 . There were 30 more Republicans then Democrats . How many Democrats and Republicans were there in the Senate ?

Direct: ['202', '232'] — correct=True; Z3: []; gold: [202.0, 232.0]

```json
{
  "status": "NOT_SUPPORTED",
  "variables": {},
  "constraints": [],
  "targets": []
}
```

### alg514/3285 — AMBIGUOUS (minmax_threshold)

Giới hạn ngân sách và hỏi số bạn tối đa; mô hình giữ bất đẳng thức nên target không duy nhất.

Đề: Mitch is buying candy bars for his friends . He wants to give 2 bars to each friend , and he wants to have 10 spare bars . He can afford to buy 24 candy bars . How many friends can he treat ?

Direct: ['7'] — correct=True; Z3: []; gold: [7.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "f": "Int",
    "b": "Int"
  },
  "constraints": [
    "2 * f + 10 == b",
    "b <= 24",
    "b >= 0",
    "f >= 0"
  ],
  "targets": [
    "f"
  ]
}
```

### alg514/3790 — ERROR (syntax)

Dùng toán tử sai cú pháp. Chuẩn hóa riêng toán tử trong bản sao cho DETERMINATE [16,50], khớp gold.

Đề: Separate 66 into 2 parts so that 0.40 of one part exceeds 0.625 of the other part by 10 . What is the smaller part ? What is the larger part ?

Direct: ['16', '50'] — correct=True; Z3: []; gold: [16.0, 50.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real",
    "y": "Real"
  },
  "constraints": [
    "x + y == 66",
    "(0.4 * x == 0.625 * y + 10) || (0.4 * y == 0.625 * x + 10)",
    "x >= 0",
    "y >= 0",
    "x <= y"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

Error: SyntaxError: invalid syntax (<unknown>, line 1)

### alg514/4035 — AMBIGUOUS (missing_or_target)

Bỏ tổng số bộ chén x+y == 250, chỉ giữ tổng tiền. Thêm quan hệ có sẵn trong nguồn sẽ cố định nghiệm.

Đề: You had 6,800.00 dollars to spend and purchased 250 sets of dishes . If you spent everything , how many 20.00 dollars sets did you purchase ? How many 45.00 dollars sets did you purchase ?

Direct: ['178', '72'] — correct=True; Z3: []; gold: [178.0, 72.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Int",
    "y": "Int"
  },
  "constraints": [
    "20 * x + 45 * y == 6800",
    "x >= 0",
    "y >= 0"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

### alg514/5298 — AMBIGUOUS (minmax_threshold)

Hỏi ngưỡng agency rẻ hơn; bất đẳng thức m>25 có nhiều nghiệm. Gold 25 là ranh giới hòa vốn.

Đề: The first agency charges 20.25 dollars per day and 0.14 dollars per mile . The second agency charges 18.25 dollars per day and 0.22 dollars per mile . How many miles would you have to drive before the first agency is less expensive than the second ?

Direct: ['25'] — correct=True; Z3: []; gold: [25.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "m": "Real"
  },
  "constraints": [
    "20.25 + 0.14 * m < 18.25 + 0.22 * m",
    "m >= 0"
  ],
  "targets": [
    "m"
  ]
}
```

### alg514/5652 — AMBIGUOUS (missing_or_target)

Thêm biến thuế chưa biết vào số tiền được nêu trước thuế, khiến mô hình thừa bậc tự do; cần dịch đúng subtotal plus tax.

Đề: You and a friend go to a Mexican restaurant . You order 2 tacos and 3 enchiladas , and your friend orders 3 tacos and 5 enchiladas . Your bill is 7.80 dollars plus tax , and your friend 's bill is 12.70 dollars plus tax . How much , in dollars , does each taco cost ? How much does each enchilada cost ?

Direct: ['0.90', '2.00'] — correct=True; Z3: []; gold: [0.9, 2.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "t": "Real",
    "e": "Real",
    "x": "Real"
  },
  "constraints": [
    "2*t + 3*e + x == 7.80",
    "3*t + 5*e + x == 12.70",
    "t >= 0",
    "e >= 0"
  ],
  "targets": [
    "t",
    "e"
  ]
}
```

### alg514/5783 — ERROR (syntax)

Sai cú pháp toán tử; chỉ sửa toán tử vẫn INCONSISTENT vì ghép nhầm vai trò số nhỏ/số lớn.

Đề: The sum of 2 numbers is 15 . 3 times one of the numbers is 11 less than 5 times the other . What is the smaller number ? What is the larger number ?

Direct: ['7', '8'] — correct=True; Z3: []; gold: [7.0, 8.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "s": "Real",
    "l": "Real"
  },
  "constraints": [
    "s + l == 15",
    "(s <= l && 3*s == 5*l - 11) || (l <= s && 3*l == 5*s - 11)",
    "s >= 0",
    "l >= 0"
  ],
  "targets": [
    "s",
    "l"
  ]
}
```

Error: SyntaxError: invalid syntax (<unknown>, line 1)

### alg514/5894 — AMBIGUOUS (minmax_threshold)

Hỏi hai số chẵn liên tiếp lớn nhất, nhưng chỉ giữ miền sum<=30; cần mục tiêu tối ưu và mã hóa tính chẵn.

Đề: The sum of two consecutive even integers is at most 30 . What are the greatest possible consecutive even integers ?

Direct: ['14', '16'] — correct=True; Z3: []; gold: [14.0, 16.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Int",
    "y": "Int"
  },
  "constraints": [
    "y == x + 2",
    "x + y <= 30",
    "x >= 0",
    "y >= 0"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

### alg514/6008 — AMBIGUOUS (missing_or_target)

Mã hóa x=3*y OR y=3*x với targets [x,y], tạo hai tuple hoán đổi. Nên đặt vai trò smaller/larger khi đề chỉ yêu cầu hai số vô danh.

Đề: 1 out of 2 numbers is thrice the other . If their sum is 124 , find the numbers .

Direct: ['31', '93'] — correct=True; Z3: []; gold: [31.0, 93.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real",
    "y": "Real"
  },
  "constraints": [
    "x + y == 124",
    "(x == 3*y) or (y == 3*x)"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

### alg514/6072 — INCONSISTENT (inconsistent)

Số áo Int nhưng phương trình hòa vốn 20*n == 1500+3*n cho n=88.23529. Gold dùng nghiệm liên tục; nếu cần số áo tối thiểu không lỗ thì là 89. Cần thống nhất miền và mục tiêu.

Đề: Suppose you invest 1,500 dollars in equipment to put pictures on T-shirts . You buy each T-shirt for 3 dollars . After you have placed the pictures on a shirt , you sell it for 20 dollars . How many T-shirts must you sell to break even ?

Direct: ['1500/17'] — correct=True; Z3: []; gold: [88.23529]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "n": "Int"
  },
  "constraints": [
    "20 * n == 1500 + 3 * n",
    "n >= 0"
  ],
  "targets": [
    "n"
  ]
}
```

### alg514/6106 — NOT_SUPPORTED (unsupported)

Từ chối quá mức: một lô vật liệu giá 20 đủ tới 20 nến; 15*n-20 == 85 cho n=7 nằm trong lô, có thể hỗ trợ.

Đề: You make candles and sell them for 15 dollars each . The material to make up to 20 candles costs 20 dollars . How many candles must you sell to have a profit of 85 dollars ?

Direct: ['7'] — correct=True; Z3: []; gold: [7.0]

```json
{
  "status": "NOT_SUPPORTED",
  "variables": {},
  "constraints": [],
  "targets": []
}
```

### alg514/6208 — ERROR (syntax)

Sai cú pháp toán tử; chỉ sửa toán tử vẫn AMBIGUOUS do vai trò hai số hoán đổi.

Đề: The carpenter saws a board that is 22 feet long into two pieces . One piece is to be 1 foot longer than twice the length of the shorter piece . Find the Length of each piece .

Direct: ['7', '15'] — correct=True; Z3: []; gold: [7.0, 15.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real",
    "y": "Real"
  },
  "constraints": [
    "x + y == 22",
    "(x >= y && x == 2*y + 1) || (y > x && y == 2*x + 1)",
    "x >= 0",
    "y >= 0"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

Error: SyntaxError: invalid syntax (<unknown>, line 1)

### alg514/6334 — AMBIGUOUS (missing_or_target)

Bỏ tổng số lần ném x+y == 20; chỉ giữ 2*x+3*y == 43.

Đề: The Lakers scored 43 points on a combination of 20 two point baskets and three point baskets . How many shots of two point baskets and how many shots of three point baskets were made ?

Direct: ['17', '3'] — correct=True; Z3: []; gold: [17.0, 3.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Int",
    "y": "Int"
  },
  "constraints": [
    "2 * x + 3 * y == 43",
    "x >= 0",
    "y >= 0"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

### alg514/6336 — AMBIGUOUS (resource_limit)

Giữ giới hạn ngân sách <=165200; gold giả định tiêu hết ngân sách, trong khi tổng diện tích đã cố định.

Đề: The Willey Farm Collective , farmed by several branches of the Willeys , has 4500 acres of land available for raising corn and wheat . The cost of raising corn is 42 dollars an acre , while the cost of wheat is 35 dollars an acre . The Collective 's available capital is 165,200 dollars . How many acres of corn should the Collective plant ? How many acres of wheat should the collective plant ?

Direct: ['1100', '3400'] — correct=True; Z3: []; gold: [1100.0, 3400.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "corn": "Real",
    "wheat": "Real"
  },
  "constraints": [
    "corn + wheat == 4500",
    "42 * corn + 35 * wheat <= 165200",
    "corn >= 0",
    "wheat >= 0"
  ],
  "targets": [
    "corn",
    "wheat"
  ]
}
```

### alg514/6348 — AMBIGUOUS (minmax_threshold)

Hỏi quãng đường tối đa dưới ngân sách; miền m<=190 không có một target duy nhất.

Đề: A car rents for 50 dollars a day plus 20 cents a mile . You are on a daily budget of 88 dollars . What maximum mileage will allow you to stay within your budget ?

Direct: ['190'] — correct=True; Z3: []; gold: [190.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real"
  },
  "constraints": [
    "50 + 0.2 * x <= 88",
    "x >= 0"
  ],
  "targets": [
    "x"
  ]
}
```

### alg514/6376 — ERROR (syntax)

Sai cú pháp toán tử; chỉ sửa toán tử vẫn AMBIGUOUS do hoán đổi vai trò hai số.

Đề: The larger of two numbers is 23 less than twice the smaller . The sum of the two numbers is 70 . Find the two numbers .

Direct: ['31', '39'] — correct=True; Z3: []; gold: [31.0, 39.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real",
    "y": "Real"
  },
  "constraints": [
    "(x >= y) -> (x == 2*y - 23)",
    "(y >= x) -> (y == 2*x - 23)",
    "x + y == 70"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

Error: SyntaxError: invalid syntax (<unknown>, line 1)

### alg514/6759 — AMBIGUOUS (minmax_threshold)

Hỏi số lần tối thiểu để mua giày hợp lý; n>=26 cần tìm min. Direct cũng sai (9).

Đề: An ice skating rink charges 5 dollars for admission and 2.50 dollars to rent skates . Jill can purchase a new pair of skates for 65 dollars . How many times would she need to go the rink to justify buying the skates rather than renting a pair ?

Direct: ['9'] — correct=False; Z3: []; gold: [26.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "n": "Int"
  },
  "constraints": [
    "n >= 0",
    "65 + 5 * n <= 7.5 * n"
  ],
  "targets": [
    "n"
  ]
}
```

### alg514/6779 — AMBIGUOUS (minmax_threshold)

Mục tiêu thu nhập tạo sales>=7750; cần giá trị tối thiểu hoặc khoảng, không phải tất cả nghiệm cùng một giá trị.

Đề: Trenton sells electronic supplies . Each week he earns 190 dollars plus commission equal to 4 % of his sales . This week his goal is to earn no less than 500 dollars . Write and solve an inequality to find the amount of sales he must make to reach his goal .

Direct: ['7750'] — correct=True; Z3: []; gold: [7750.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real"
  },
  "constraints": [
    "190 + 0.04 * x >= 500"
  ],
  "targets": [
    "x"
  ]
}
```

### alg514/6803 — ERROR (syntax)

Dùng & và | trong biểu thức không được compiler hỗ trợ; chuẩn hóa toán tử vẫn AMBIGUOUS do hoán đổi vai trò.

Đề: The greater of two numbers is 8 times the lesser and their sum is 180 . Find the numbers .

Direct: ['20', '160'] — correct=True; Z3: []; gold: [20.0, 160.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real",
    "y": "Real"
  },
  "constraints": [
    "x + y == 180",
    "(x >= y & x == 8 * y) | (y >= x & y == 8 * x)",
    "x >= 0",
    "y >= 0"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

Error: ValueError: Unsupported expression: (x >= y & x == 8 * y) | (y >= x & y == 8 * x)

### alg514/6831 — DETERMINATE (determinate_wrong)

Bỏ half trong vận tốc gió ngược: dùng b-w=30 thay b-0.5*w=30. Gold w=80,b=70; Direct cũng bỏ half.

Đề: Flying with the wind , a bird was able to make 150 kilometers per hour . If the wind was 0.5 times as strong and the bird flies against it , it could make only 30 kilometers per hour . Find the velocity of the wind in kilometers per hour . Find the velocity of the bird .

Direct: ['60', '90'] — correct=False; Z3: ['60', '90']; gold: [80.0, 70.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "w": "Real",
    "b": "Real"
  },
  "constraints": [
    "b + w == 150",
    "b - w == 30",
    "b >= 0",
    "w >= 0"
  ],
  "targets": [
    "w",
    "b"
  ]
}
```

### alg514/6853 — INCONSISTENT (inconsistent)

Nguồn nói headwind khi đi East nhưng thời gian East ngắn hơn West. Dịch sát headwind cho w<0, xung đột w>=0; gold đảo dấu để ra 450,50.

Đề: A direct flight on delta air lines from Atlanta to Paris is 4000 miles and takes approximately 8 hours going East and 10 hours going West . Although the plane averages the same airspeed , there is a headwind while traveling East , resulting in a different air speeds . What is the average air speed of the plane in miles per hour and the average wind speed ?

Direct: ['450/1', '50/1'] — correct=True; Z3: []; gold: [450.0, 50.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "a": "Real",
    "w": "Real"
  },
  "constraints": [
    "(a - w) * 8 == 4000",
    "(a + w) * 10 == 4000",
    "a >= 0",
    "w >= 0"
  ],
  "targets": [
    "a",
    "w"
  ]
}
```

### alg514/6878 — ERROR (syntax)

Dùng & và | ngoài compiler; sửa toán tử vẫn AMBIGUOUS do hoán đổi vai trò.

Đề: The sum of two numbers is 62 . The greater number exceeds twice the smaller number by 5 . What are the two numbers ?

Direct: ['43', '19'] — correct=True; Z3: []; gold: [19.0, 43.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Real",
    "y": "Real"
  },
  "constraints": [
    "x + y == 62",
    "(x >= y & x == 2 * y + 5) | (y >= x & y == 2 * x + 5)"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```

Error: ValueError: Unsupported expression: (x >= y & x == 2 * y + 5) | (y >= x & y == 2 * x + 5)

### alg514/6958 — AMBIGUOUS (missing_or_target)

Bỏ tổng số xe cars+trucks == 32; chỉ giữ 4*cars+6*trucks == 148.

Đề: During a 4th of July weekend , 32 vehicles became trapped on the Sunshine Skyway Bridge while it was being repaved . A recent city ordinance decreed that only cars with 4 wheels and trucks with six wheels could be on the bridge at any given time . If there were 148 tires that needed to be replaced to due to damage , how many cars and trucks were involved in the incident ?

Direct: ['22', '10'] — correct=True; Z3: []; gold: [22.0, 10.0]

```json
{
  "status": "SUPPORTED",
  "variables": {
    "x": "Int",
    "y": "Int"
  },
  "constraints": [
    "4 * x + 6 * y == 148",
    "x >= 0",
    "y >= 0"
  ],
  "targets": [
    "x",
    "y"
  ]
}
```
