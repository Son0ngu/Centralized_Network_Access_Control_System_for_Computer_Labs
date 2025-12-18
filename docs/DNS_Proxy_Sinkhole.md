# Hướng dẫn triển khai Agent làm DNS proxy/sinkhole cục bộ

Tài liệu này tóm tắt các phase chính và hướng dẫn tiếp cận khi triển khai agent đóng vai trò DNS proxy/sinkhole cục bộ để giải quyết bài toán default-deny, domain nhiều IP và tránh race condition giữa DNS và firewall.

## 1) Khảo sát & Thiết kế
- **Kiến trúc DNS**: Xác định cách ép toàn bộ truy vấn DNS về 127.0.0.1 (chính sách DHCP, GPO, MDM; chặn DoH/DoT ngoại lệ ở firewall). Ghi rõ resolver upstream tin cậy và chính sách fallback.
- **Phạm vi whitelist**: Thu thập domain/subdomain cần cho phép, hỗ trợ wildcard và preset cho bên thứ ba (CDN, analytics, font, quảng cáo nếu cần).
- **Luồng cấp phép**: Xác định quy trình: nhận truy vấn → kiểm whitelist → (nếu khớp) forward upstream → thêm IP vào firewall trước khi trả lời → trả đáp DNS.
- **Ràng buộc bảo mật**: Quy định ràng buộc domain ↔ cert (CN/SAN) để giảm spoof, TTL tối đa, negative TTL, và chính sách thu hồi IP khi TTL hết hạn.

### Rà soát kế hoạch chi tiết (Refactor roadmap)
- **Phase 1 – Kiến trúc**: Khi thiết kế module mới (dns_proxy, network_manager, security), cần xác định rõ module nào thay thế PacketSniffer cũ và module nào giữ lại để quan sát bypass (SNI/Host). Tránh duy trì song song hai kênh quyết định whitelist nếu không có quy tắc ưu tiên.
- **Phase 2 – DNS core**: Luồng “giữ đáp DNS tới khi add firewall xong” cần timeout rõ ràng (ví dụ 2–5 giây) để tránh treo truy vấn khi firewall lỗi. Cache phải tôn trọng TTL và negative TTL, nhưng nên thêm ngưỡng TTL tối thiểu (min-TTL) để hạn chế việc xoá rule quá sớm khi upstream trả TTL rất thấp.
- **Phase 3 – Adapter/DNS config**: Bổ sung kiểm tra IPv6: đặt DNS ::1 cho adapter có IPv6 và chặn DoH/DoT qua IPv6. Với máy có 2 adapter cùng up, cần chính sách ưu tiên default route nhưng vẫn khóa DNS trên adapter phụ (để tránh route-bypass). Nên có chế độ “read-only/monitor” để kiểm thử trước khi tự động thay DNS hàng loạt.
- **Phase 4 – DoH/DoT**: Blocklist DoH không chỉ dựa vào IP tĩnh; cần chặn theo SNI/Host phổ biến và cổng 443/853, kèm theo rule outbound DNS duy nhất cho 127.0.0.1 và resolver upstream đã đăng ký. Ghi rõ cách cập nhật danh sách DoH provider định kỳ.
- **Phase 5 – Firewall sync**: TTL cleanup nên xử lý batch và có grace-period ngắn (ví dụ TTL + 30–60s) để tránh xoá rule khi người dùng đang giữ kết nối dài. Rule nên ràng buộc profile (Private/Public/VPN) hoặc interface name để khớp với adapter tương ứng.
- **Phase 8 – Testing**: Bổ sung bài test “firewall thất bại”: mô phỏng add rule lỗi nhưng DNS vẫn trả lời → đảm bảo agent trả NXDOMAIN hoặc retry thay vì để kết nối rơi vào default-deny. Thêm test cho IPv6 DoH/DoT và scenario nhiều adapter cùng lúc lên/xuống.

### Checklist tự động hóa cần có
- Agent tự **gán DNS của adapter** về 127.0.0.1 khi cài/khởi động và lưu cấu hình cũ để khôi phục khi gỡ/stop.
- Định kỳ/đột xuất **kiểm tra drift** (DNS bị đổi lại) và tự áp dụng lại; log sự kiện để admin biết nếu người dùng cố tình sửa.
- Tự **thêm rule chặn DNS/DoH/DoT outbound** tới đích khác 127.0.0.1 và resolver upstream được cho phép, tránh yêu cầu người dùng tự thao tác firewall.
- Khi kết nối VPN/đổi mạng, agent tự phát hiện và **re-apply DNS + rule chặn** nếu adapter thay đổi.
- **Nhiều adapter đồng thời (Ethernet + Wi-Fi/VPN)**: Agent phải xem xét tất cả adapter đang up, áp cấu hình DNS 127.0.0.1 và rule chặn DoH/DoT cho từng adapter/profile. Không nên chỉ đặt “adapter đang active” vì người dùng có thể cắm thêm card USB hoặc bật Wi-Fi song song và bypass được nếu không bị khóa. Ghi log adapter nào bị sửa/khôi phục.

## 2) Xây dựng & Hiệu chỉnh Agent DNS
- **DNS listener**: Chạy server trên UDP/TCP 53 localhost; hỗ trợ cả IPv4/IPv6; xử lý song song nhiều truy vấn.
- **Kiểm tra whitelist sớm**: Trả NXDOMAIN/0.0.0.0 ngay nếu không khớp whitelist/wildcard để chặn từ bước DNS.
- **Forward có kiểm soát**: Chỉ forward tới resolver upstream đã định; ghi log truy vấn/đáp ứng; tôn trọng EDNS/size để tránh cắt gói.
- **Cập nhật firewall theo TTL**: Với mỗi bản ghi A/AAAA nhận được, thêm rule allow (theo profile/time-bound). Lên lịch tự gỡ rule khi TTL hết hạn hoặc khi thấy bản ghi thay đổi.
- **Chống race condition**: Giữ đáp án DNS cho tới khi thao tác firewall hoàn tất (đồng bộ hoặc queue). Sau đó mới trả lời client.
- **Quan sát SNI/Host (tùy chọn)**: Nếu thấy IP mới phát sinh qua SNI/Host hợp lệ nhưng chưa có DNS, kích hoạt prefetch/resolve lại để cập nhật IP.
  
### Tự động hóa hỗ trợ người dùng
- Agent tự **phát hiện adapter chính** (Ethernet/Wi-Fi/VPN) và apply cấu hình DNS/route phù hợp, tránh yêu cầu người dùng chọn tay.
- Cung cấp **health-check nội bộ** (CLI/UI) hiển thị trạng thái “DNS đang trỏ về 127.0.0.1, rule chặn DoH/DoT đang bật” để người dùng không phải tự kiểm thủ công.
- Tự **khôi phục cấu hình mạng** khi stop/uninstall để không làm gián đoạn kết nối internet.
- **Khóa cứng trên multi-adapter**: Khi phát hiện thêm adapter mới (hotplug) hoặc trạng thái lên/xuống, chạy lại bộ áp dụng DNS 127.0.0.1 + rule chặn cho adapter mới. Ưu tiên adapter có default route, nhưng vẫn giữ chặn trên adapter phụ để tránh lộ lưu lượng qua “đường vòng”. Nếu hệ điều hành hỗ trợ, dùng chính sách per-interface (ví dụ Windows: netsh interface ipv4 add dnsserver name="<interface>" address=127.0.0.1 index=1; firewall rule ràng buộc InterfaceType/InterfaceAlias).

## 3) Chính sách bảo mật bổ sung
- **Chặn bypass DNS**: Chặn outbound DNS/DoH/DoT khác ngoài 127.0.0.1 và resolver upstream được phép; giám sát log để phát hiện nỗ lực bypass.
- **Ràng buộc cert**: Khi cấp phép tạm dựa trên SNI/Host, kiểm tra chứng chỉ khớp domain; nếu lệch, block và ghi nhận.
- **Giới hạn phạm vi rule**: Rule firewall nên gắn session/TTL ngắn, chỉ mở port cần thiết (80/443 hoặc tùy ứng dụng), ưu tiên outbound, tránh mở rộng inbound nếu không cần.

## 4) Vận hành & Giám sát
- **Logging chuẩn hóa**: Ghi lại truy vấn, quyết định allow/deny, IP cấp phép, TTL, thời điểm gỡ rule, lý do chặn (không khớp whitelist, cert mismatch, bypass DNS...).
- **Đồng bộ tập trung**: Nếu có control-plane, đồng bộ whitelist, preset domain và nhận lệnh cập nhật. Đảm bảo agent báo trạng thái (health, số rule hiện hành).
- **Cảnh báo & phản ứng**: Thiết lập alert khi thấy nhiều NXDOMAIN bất thường, nỗ lực dùng DoH, hoặc chứng chỉ không khớp lặp lại.
- **Kiểm thử định kỳ**: Giả lập domain nhiều IP, thay đổi TTL, kiểm thử failover của resolver upstream và độ trễ thêm rule firewall.
  
### Kiểm soát drift & tự phục hồi
- Thiết lập **watcher** theo dõi thay đổi DNS server ở OS/via DHCP; nếu phát hiện lệch khỏi 127.0.0.1 thì tự sửa và cảnh báo.
- Định kỳ kiểm tra **rule chặn DoH/DoT** và rule allow tạm theo TTL còn hợp lệ; tự dọn các rule mồ côi.
- Nếu agent crash/restart, có **startup hook** để re-apply toàn bộ rule và adapter DNS trước khi xử lý truy vấn đầu tiên.

## 5) Triển khai & Rollout an toàn
- **Staging**: Triển khai thử trên một nhóm máy, bật log chi tiết và TTL ngắn để quan sát tác động.
- **Rollback**: Chuẩn bị cơ chế gỡ agent hoặc chuyển DNS về resolver cũ nhanh chóng nếu gặp sự cố.
- **Tối ưu hiệu năng**: Cache DNS hợp lệ trong thời gian TTL, giới hạn concurrency và timeout hợp lý với resolver upstream để tránh bão truy vấn.

## 6) Tài liệu & Hỗ trợ người dùng
- **Hướng dẫn cấu hình**: Viết rõ cách cấu hình DNS về 127.0.0.1, cách khai báo whitelist, và quy trình hỗ trợ khi domain mới bị chặn.
- **FAQ sự cố**: Không resolve được, web chậm, cert mismatch, DoH bị block… kèm bước kiểm tra và log cần cung cấp.

## 7) Kế hoạch mở rộng (tùy chọn)
- **Bundle/preset domain**: Cho phép khai báo gói domain phụ trợ (API, static, CDN, analytics) đi kèm domain chính.
- **API/SDK tích hợp**: Cung cấp API để ứng dụng nội bộ tự đăng ký domain/TTL tạm thời (just-in-time access) có kiểm soát.
- **Hỗ trợ nhiều resolver**: Triển khai load balancing/failover cho resolver upstream, ưu tiên DNSSEC nếu hạ tầng hỗ trợ.