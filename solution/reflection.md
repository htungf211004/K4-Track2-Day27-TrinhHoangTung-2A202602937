# Reflection

**Lỗi khó nhất và cách xử lý**

Lỗi phân phối nhẹ và training-serving skew khó phân biệt với dao động sạch.
Tôi giữ kiểm tra đơn chiều theo baseline và bổ sung khoảng cách đa chiều cho
data_batch. Rows và mean được chuẩn hóa bằng nửa khoảng baseline (biên 3σ),
null và staleness bằng giới hạn tương ứng; ngưỡng tổng hợp là 1,30. Đây là
điểm số heuristic, không phải khoảng cách Mahalanobis hay xác suất lỗi.

Theo hướng dẫn được cung cấp, ngưỡng feature là 0,65σ, embedding centroid là
0,040 và tuổi corpus là 45 ngày. Các ngưỡng được cố định trước khi chạy Public.
Lineage kiểm tra cả mất upstream, output không có downstream và runtime;
fallback upstream áp dụng cho topology stg_orders của lab. Contract kiểm tra
violations, SLA khai báo và độ trễ vượt baseline, với lý do riêng cho từng loại.

Practice đạt 50,0 điểm: TP=33, FP=0, FN=0, TN=87, chi phí 180/220 credits.
Đối chiếu độc lập theo seq kiểm tra đủ 120 sự kiện và tính lại điểm.
Public đạt 46,9 điểm, bốn pillar đều high, chi phí 240/220 credits. Private
chính thức đạt 32,41 điểm: TPR=64,81%, FPR=0%, không vượt ngân sách. Kết quả
cho thấy còn bỏ sót lỗi tinh vi dù kiểm soát tốt báo động giả. Tôi giữ nguyên
bộ phát hiện trước và sau lần chạy Private, không chỉnh theo phản hồi cuối.

**Đánh đổi chi phí và cải tiến tiếp theo**

Mỗi event gọi một tool đúng loại, không gọi lại và không bỏ event khi ngân sách
âm. Public vượt 20 credits, tương ứng phạt khoảng 1,82 điểm; tôi chấp nhận mức
phạt để giữ coverage. Metadata khai báo không chứng minh trạng thái thực tế
sạch nên chưa đủ căn cứ để bỏ qua RPC.

Nếu có thêm thời gian, tôi sẽ dùng ctx.state lưu cửa sổ số đo theo từng bảng,
feature view và corpus, rồi ước lượng median/MAD sau giai đoạn khởi động.
Chỉ cập nhật từ các mẫu có độ tin cậy sạch cao để hạn chế baseline nhiễm lỗi.
Tôi sẽ thử hiệu chỉnh tương quan giữa các chỉ số trên dữ liệu sạch độc lập và
kiểm tra ngưỡng trên nhiều stream. Cache chỉ dùng cho đối tượng cùng phiên
bản lặp lại; giảm chi phí phải được cân với mất TPR và tăng FPR. FPR=0 chưa
đủ để đạt điểm tối ưu khi TPR còn thấp.
