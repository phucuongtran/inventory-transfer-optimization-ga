# Inventory Transfer Optimization

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![pandas](https://img.shields.io/badge/pandas-%E2%89%A51.3-150458)
![networkx](https://img.shields.io/badge/networkx-graph-orange)

Hệ thống đề xuất **điều chuyển hàng tồn kho giữa các cửa hàng** trong một chuỗi bán lẻ: cửa hàng nào gửi bao nhiêu đơn vị sản phẩm nào sang cửa hàng nào, để **lấp chỗ thiếu hàng** bằng hàng đang **tồn dư** ở nơi khác, với **chi phí vận chuyển thấp nhất**.

Dự án so sánh hai cách tiếp cận:

- **Rule-based (tham lam):** lấp chỗ thiếu lớn nhất trước, lấy hàng từ cửa hàng gần nhất trước.
- **Genetic Algorithm (tự cài đặt):** tiến hoá một quần thể kế hoạch để tối thiểu *chi phí vận chuyển + phạt cho phần nhu cầu chưa được lấp*.

## Cách hoạt động

```mermaid
flowchart LR
    A[Dữ liệu bán hàng<br/>+ tồn kho] --> B["Phân tích:<br/>số ngày tồn kho<br/>→ Thừa / Thiếu / Cân bằng"]
    B --> C[Rule-based]
    B --> D[Genetic Algorithm]
    C --> E["So sánh & chọn<br/>kế hoạch tốt nhất"]
    D --> E
    E --> F[Báo cáo CSV / TXT]
    E --> G[Mạng lưới GraphML + PNG]
```

1. **Phân tích:** với mỗi cặp (cửa hàng, sản phẩm), tính `số ngày tồn kho = tồn hiện tại / lượng bán trung bình mỗi ngày`.
   - Dưới **7 ngày** → *thiếu*.
   - Trên **21 ngày** → *thừa*.
2. **Tối ưu:** hai thuật toán đề xuất kế hoạch điều chuyển. Kế hoạch không bao giờ lấy quá phần dư, cũng không gửi quá phần thiếu.
3. **Đánh giá:** mô phỏng tồn kho sau khi điều chuyển và so sánh trước/sau (số mặt hàng thiếu/thừa, độ lệch tồn kho, giá trị tồn dư).
4. **Chọn kế hoạch:** ưu tiên kế hoạch giải quyết **nhiều mặt hàng thiếu nhất**; nếu hoà thì chọn kế hoạch **rẻ hơn**.

Cước vận chuyển mỗi đơn vị = `2.000 VND/km × khoảng cách × hệ số liên tỉnh × hệ số cự ly`, với khoảng cách tính bằng công thức haversine từ toạ độ cửa hàng.

## Cài đặt

Yêu cầu: **Python 3.9 trở lên**.

```bash
git clone <url-repo-cua-ban>
cd <ten-thu-muc-repo>

python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

Hoặc dùng conda:

```bash
conda env create -f environment.yml
conda activate inventory_optimization
```

## Chạy

Repo **không kèm dữ liệu**. Lần chạy đầu tiên cần sinh dữ liệu mẫu: 20 cửa hàng ở Hà Nội, Đà Nẵng, TP.HCM; 30 sản phẩm; 90 ngày bán hàng.

```bash
python src/main.py --generate-data --all --network
```

Các lần sau, dữ liệu đã có trong `data/`:

```bash
python src/main.py --all              # chạy cả 2 thuật toán và so sánh
python src/main.py --rule-based       # chỉ thuật toán tham lam
python src/main.py --ga               # chỉ Genetic Algorithm
python src/main.py --all --network    # kèm xuất mạng lưới GraphML + biểu đồ
python src/main.py                    # chỉ phân tích tồn kho
```

Có thể chạy từ bất kỳ thư mục nào; `python -m src.main ...` cũng cho kết quả tương tự.

### Tuỳ chọn thường dùng

| Tuỳ chọn | Mặc định | Ý nghĩa |
|---|---|---|
| `--generate-data` | tắt | Sinh dữ liệu mẫu (ghi đè `data/`) |
| `--rule-based` / `--ga` / `--all` | tắt | Thuật toán cần chạy |
| `--network` | tắt | Xuất mạng lưới điều chuyển (GraphML + 3 ảnh PNG) |
| `--min-days` / `--max-days` | 7 / 21 | Ngưỡng thiếu / thừa (số ngày tồn kho) |
| `--seed` | 2025 | Seed ngẫu nhiên để tái lập kết quả |
| `--products` / `--days` | 30 / 90 | Kích thước dữ liệu mẫu |
| `--ga-population` / `--ga-generations` | 50 / 50 | Kích thước quần thể / số thế hệ của GA |
| `--ga-penalty` | 2.000.000 | Tiền phạt (VND) cho mỗi đơn vị thiếu chưa được lấp |
| `--data-dir` / `--results-dir` / `--vis-dir` | `data/` / `results/` / `visualizations/` | Thư mục vào/ra |

Xem đầy đủ bằng `python src/main.py --help`. Mọi giá trị mặc định nằm trong `src/config.py`.

### Notebook

```bash
jupyter notebook notebooks/01_full_process_step_by_step.ipynb
```

Notebook chạy lại toàn bộ quy trình từng bước, có biểu đồ khám phá dữ liệu, đường cong fitness của GA và bảng so sánh hai thuật toán.

## Kết quả đầu ra

| File | Nội dung |
|---|---|
| `results/result_summary.txt` | So sánh hai thuật toán và kế hoạch được đề xuất |
| `results/best_transfer_plan.csv` | Danh sách điều chuyển: gửi từ, gửi đến, sản phẩm, số lượng, cước |
| `results/inventory_analysis.csv` | Trạng thái tồn kho của từng cặp cửa hàng – sản phẩm |
| `results/rule_based_*.csv`, `results/ga_*.csv` | Kế hoạch và bảng tác động trước/sau của từng thuật toán |
| `visualizations/*.graphml`, `*.png` | Mạng lưới điều chuyển (mở bằng Gephi / yEd / Cytoscape) |

Ví dụ trên một bộ dữ liệu mẫu (seed 2025, 600 cặp cửa hàng – sản phẩm, 128 mặt hàng thiếu):

| | Rule-based | Genetic Algorithm |
|---|---|---|
| Thời gian chạy | < 0,1 s | ~1,5 s |
| Đơn vị thiếu được lấp | 100% | ~99% |
| Mặt hàng thiếu được giải quyết | 128 / 128 | 112 / 128 |
| Tổng cước vận chuyển | ~309 triệu VND | ~1,6 tỷ VND |

Trên dữ liệu mẫu, thuật toán tham lam đang cho kết quả tốt hơn GA. Hướng cải thiện GA: khởi tạo quần thể từ lời giải tham lam, dùng toán tử đột biến có định hướng và tăng số thế hệ.

> Dữ liệu mẫu có ngày cuối là ngày chạy lệnh, nên mỗi lần sinh lại số liệu sẽ khác một chút.

## Cấu trúc dự án

```
├── src/
│   ├── main.py               # Điểm vào CLI
│   ├── config.py             # Toàn bộ tham số
│   ├── engine/               # Phân tích, 2 thuật toán, báo cáo
│   ├── data_generator/       # Sinh dữ liệu mẫu
│   ├── visualization/        # GraphML + biểu đồ mạng lưới
│   └── utils/                # Logging
├── notebooks/                # Notebook phân tích từng bước
├── visualizations/           # Kết quả mạng lưới
├── requirements.txt
└── environment.yml
```

## Dùng dữ liệu của bạn

Đặt 6 file CSV vào một thư mục rồi chạy `python src/main.py --all --data-dir <thư-mục>`:

| File | Cột |
|---|---|
| `stores.csv` | `store_id, store_name, city, latitude, longitude` |
| `products.csv` | `product_id, product_name, category, price, cost` |
| `sales_data.csv` | `date, store_id, product_id, quantity, revenue, cost` |
| `inventory_data.csv` | `store_id, product_id, current_stock, last_updated` |
| `distance_matrix.csv` | Ma trận vuông khoảng cách (km), nhãn hàng/cột là `store_id` |
| `transport_cost_matrix.csv` | Ma trận vuông cước mỗi đơn vị (VND), đường chéo để trống |

## Công nghệ

Python · pandas · numpy · networkx · matplotlib · tqdm · Jupyter. Genetic Algorithm được tự cài đặt, không dùng thư viện tối ưu bên ngoài.
