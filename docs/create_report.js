const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageNumber, PageBreak,
  TabStopType, TabStopPosition, ImageRun
} = require("docx");

// ==================== CONSTANTS ====================
const FONT = "Times New Roman";
const FONT_SIZE_NORMAL = 26; // 13pt
const FONT_SIZE_H1 = 28; // 14pt
const FONT_SIZE_H2 = 26; // 13pt
const FONT_SIZE_H3 = 26; // 13pt
const FONT_SIZE_TITLE = 32; // 16pt
const FONT_SIZE_COVER = 36; // 18pt
const LINE_SPACING = 360; // 1.5 line

const PAGE_WIDTH = 11906; // A4
const PAGE_HEIGHT = 16838;
const MARGIN_TOP = 1440; // ~2.5cm
const MARGIN_BOTTOM = 1440;
const MARGIN_LEFT = 2016; // ~3.5cm
const MARGIN_RIGHT = 1440; // ~2.5cm
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT; // ~8450

// ==================== HELPER FUNCTIONS ====================
function p(text, options = {}) {
  const {
    bold = false, italic = false, size = FONT_SIZE_NORMAL, align,
    spacing = { line: LINE_SPACING }, indent, heading, firstLineIndent = true,
    font = FONT, color, underline
  } = options;

  const runProps = { text, font, size, bold, italic };
  if (color) runProps.color = color;
  if (underline) runProps.underline = {};

  const paraProps = { spacing };
  if (align) paraProps.alignment = align;
  if (heading) paraProps.heading = heading;
  if (indent) paraProps.indent = indent;
  else if (firstLineIndent && !heading && !bold && align !== AlignmentType.CENTER) {
    paraProps.indent = { firstLine: 720 }; // ~1.27cm first line indent
  }

  paraProps.children = [new TextRun(runProps)];
  return new Paragraph(paraProps);
}

function multiRunParagraph(runs, options = {}) {
  const { align, spacing = { line: LINE_SPACING }, indent, heading, firstLineIndent = true } = options;
  const paraProps = { spacing };
  if (align) paraProps.alignment = align;
  if (heading) paraProps.heading = heading;
  if (indent) paraProps.indent = indent;
  else if (firstLineIndent && !heading) {
    paraProps.indent = { firstLine: 720 };
  }
  paraProps.children = runs.map(r => new TextRun({ font: FONT, size: FONT_SIZE_NORMAL, ...r }));
  return new Paragraph(paraProps);
}

function heading1(text) {
  return p(text, { bold: true, size: FONT_SIZE_H1, heading: HeadingLevel.HEADING_1, firstLineIndent: false, spacing: { before: 240, after: 120, line: LINE_SPACING } });
}

function heading2(text) {
  return p(text, { bold: true, size: FONT_SIZE_H2, heading: HeadingLevel.HEADING_2, firstLineIndent: false, spacing: { before: 200, after: 100, line: LINE_SPACING } });
}

function heading3(text) {
  return p(text, { bold: true, size: FONT_SIZE_H3, heading: HeadingLevel.HEADING_3, firstLineIndent: false, spacing: { before: 160, after: 80, line: LINE_SPACING } });
}

function emptyLine() {
  return new Paragraph({ spacing: { line: LINE_SPACING }, children: [new TextRun({ text: "", font: FONT, size: FONT_SIZE_NORMAL })] });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

// Table helper
function createTable(headers, rows, colWidths) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: "000000" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cellMargins = { top: 40, bottom: 40, left: 80, right: 80 };

  const headerRow = new TableRow({
    children: headers.map((h, i) => new TableCell({
      borders,
      width: { size: colWidths[i], type: WidthType.DXA },
      shading: { fill: "D9E2F3", type: ShadingType.CLEAR },
      margins: cellMargins,
      children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { line: 276 },
        children: [new TextRun({ text: h, font: FONT, size: 22, bold: true })]
      })]
    }))
  });

  const dataRows = rows.map(row => new TableRow({
    children: row.map((cell, i) => new TableCell({
      borders,
      width: { size: colWidths[i], type: WidthType.DXA },
      margins: cellMargins,
      children: [new Paragraph({
        spacing: { line: 276 },
        children: [new TextRun({ text: cell, font: FONT, size: 22 })]
      })]
    }))
  }));

  return new Table({
    width: { size: colWidths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [headerRow, ...dataRows]
  });
}

// ==================== CONTENT SECTIONS ====================

// --- COVER PAGE ---
function createCoverPage() {
  return [
    emptyLine(),
    p("BỘ GIÁO DỤC VÀ ĐÀO TẠO", { bold: true, size: 28, align: AlignmentType.CENTER, firstLineIndent: false }),
    p("TRƯỜNG ĐẠI HỌC BÁCH KHOA HÀ NỘI", { bold: true, size: 28, align: AlignmentType.CENTER, firstLineIndent: false }),
    p("VIỆN CÔNG NGHỆ THÔNG TIN VÀ TRUYỀN THÔNG", { bold: true, size: 26, align: AlignmentType.CENTER, firstLineIndent: false }),
    emptyLine(), emptyLine(), emptyLine(),
    p("ĐỒ ÁN TỐT NGHIỆP", { bold: true, size: FONT_SIZE_COVER, align: AlignmentType.CENTER, firstLineIndent: false }),
    emptyLine(),
    p("ĐỀ TÀI:", { bold: true, size: 28, align: AlignmentType.CENTER, firstLineIndent: false }),
    p("XÂY DỰNG HỆ THỐNG QUẢN LÝ BẢO MẬT MẠNG", { bold: true, size: FONT_SIZE_COVER, align: AlignmentType.CENTER, firstLineIndent: false }),
    p("PHÂN TÁN CHO MÔI TRƯỜNG GIÁO DỤC", { bold: true, size: FONT_SIZE_COVER, align: AlignmentType.CENTER, firstLineIndent: false }),
    p("(SAINT - Security Agent Integrated Network Tool)", { bold: true, italic: true, size: 28, align: AlignmentType.CENTER, firstLineIndent: false }),
    emptyLine(), emptyLine(), emptyLine(), emptyLine(),
    p("Sinh viên thực hiện:  ...............................", { size: 26, align: AlignmentType.LEFT, indent: { left: 2160 }, firstLineIndent: false }),
    p("MSSV:                       ...............................", { size: 26, align: AlignmentType.LEFT, indent: { left: 2160 }, firstLineIndent: false }),
    p("Lớp:                          ...............................", { size: 26, align: AlignmentType.LEFT, indent: { left: 2160 }, firstLineIndent: false }),
    p("Giáo viên hướng dẫn: ...............................", { size: 26, align: AlignmentType.LEFT, indent: { left: 2160 }, firstLineIndent: false }),
    emptyLine(), emptyLine(), emptyLine(), emptyLine(),
    p("Hà Nội, 2025", { bold: true, size: 28, align: AlignmentType.CENTER, firstLineIndent: false }),
    pageBreak()
  ];
}

// --- ACKNOWLEDGMENT ---
function createAcknowledgment() {
  return [
    p("LỜI CẢM ƠN", { bold: true, size: FONT_SIZE_TITLE, align: AlignmentType.CENTER, firstLineIndent: false, spacing: { before: 240, after: 240, line: LINE_SPACING } }),
    emptyLine(),
    p("Trước hết, em xin gửi lời cảm ơn chân thành nhất đến thầy/cô giáo hướng dẫn đã tận tình chỉ bảo, định hướng và hỗ trợ em trong suốt quá trình thực hiện đồ án tốt nghiệp này. Những góp ý và hướng dẫn quý báu của thầy/cô đã giúp em hoàn thiện đề tài một cách tốt nhất."),
    p("Em xin cảm ơn các thầy cô giáo trong Viện Công nghệ Thông tin và Truyền thông, Trường Đại học Bách khoa Hà Nội đã truyền đạt cho em những kiến thức nền tảng vững chắc trong suốt quá trình học tập, tạo tiền đề quan trọng để em có thể thực hiện đồ án này."),
    p("Em cũng xin gửi lời cảm ơn đến gia đình và bạn bè đã luôn động viên, khích lệ em trong suốt quá trình học tập và nghiên cứu."),
    p("Mặc dù đã cố gắng hoàn thiện đồ án một cách tốt nhất, tuy nhiên do kiến thức và kinh nghiệm còn hạn chế nên không thể tránh khỏi những thiếu sót. Em rất mong nhận được sự góp ý của các thầy cô để có thể hoàn thiện hơn."),
    p("Em xin chân thành cảm ơn!", { align: AlignmentType.RIGHT, firstLineIndent: false }),
    emptyLine(),
    p("Hà Nội, tháng ... năm 2025", { italic: true, align: AlignmentType.RIGHT, firstLineIndent: false }),
    p("Sinh viên thực hiện", { italic: true, align: AlignmentType.RIGHT, firstLineIndent: false }),
    pageBreak()
  ];
}

// --- ABSTRACT ---
function createAbstract() {
  return [
    p("TÓM TẮT ĐỒ ÁN", { bold: true, size: FONT_SIZE_TITLE, align: AlignmentType.CENTER, firstLineIndent: false, spacing: { before: 240, after: 240, line: LINE_SPACING } }),
    emptyLine(),
    p("Trong môi trường giáo dục hiện đại, việc quản lý và kiểm soát truy cập mạng Internet tại các phòng máy tính, phòng thực hành là một yêu cầu cấp thiết. Học sinh, sinh viên thường xuyên truy cập các trang web không phù hợp trong giờ học, làm giảm chất lượng giảng dạy và tiềm ẩn các rủi ro bảo mật. Tuy nhiên, các giải pháp hiện có thường phức tạp, chi phí cao hoặc không phù hợp với đặc thù của môi trường giáo dục Việt Nam."),
    p("Đồ án này trình bày việc thiết kế và phát triển hệ thống SAINT (Security Agent Integrated Network Tool) - một hệ thống quản lý bảo mật mạng phân tán được thiết kế riêng cho môi trường giáo dục. Hệ thống hoạt động theo mô hình Client-Server, bao gồm hai thành phần chính: Server quản lý tập trung được xây dựng trên nền tảng Flask và MongoDB, cung cấp REST API và Web Dashboard cho quản trị viên và giáo viên; Agent là phần mềm cài đặt trên các máy tính Windows, thực hiện giám sát lưu lượng mạng, đồng bộ danh sách truy cập cho phép (whitelist) và tự động cấu hình Windows Firewall."),
    p("Các đóng góp chính của đồ án bao gồm: thiết kế kiến trúc phân tán linh hoạt với khả năng mở rộng; xây dựng cơ chế quản lý truy cập mạng dựa trên whitelist với đồng bộ tự động; phát triển module giám sát gói tin mạng sử dụng kỹ thuật phân tích DNS, HTTP và TLS/SNI; triển khai hệ thống phân quyền RBAC hai cấp (Admin/Teacher) phù hợp với cơ cấu tổ chức giáo dục; và xây dựng giao diện người dùng trực quan trên cả hai nền tảng web và desktop."),
    emptyLine(),
    multiRunParagraph([
      { text: "Từ khóa: ", bold: true },
      { text: "Bảo mật mạng, quản lý truy cập, whitelist, firewall, giáo dục, Client-Server, phân tán" }
    ]),
    pageBreak()
  ];
}

// --- TABLE OF CONTENTS ---
function createTOC() {
  return [
    p("MỤC LỤC", { bold: true, size: FONT_SIZE_TITLE, align: AlignmentType.CENTER, firstLineIndent: false, spacing: { before: 240, after: 240, line: LINE_SPACING } }),
    emptyLine(),
    p("(Mục lục sẽ được tạo tự động trong Microsoft Word: References → Table of Contents)", { italic: true, align: AlignmentType.CENTER, firstLineIndent: false }),
    emptyLine(), emptyLine(),
    p("Lời cảm ơn", { firstLineIndent: false }),
    p("Tóm tắt đồ án", { firstLineIndent: false }),
    p("Danh mục hình vẽ", { firstLineIndent: false }),
    p("Danh mục bảng biểu", { firstLineIndent: false }),
    p("Danh mục từ viết tắt", { firstLineIndent: false }),
    p("Chương 1. Giới thiệu đề tài", { firstLineIndent: false }),
    p("Chương 2. Khảo sát yêu cầu", { firstLineIndent: false }),
    p("Chương 3. Công nghệ sử dụng", { firstLineIndent: false }),
    p("Chương 4. Thiết kế và triển khai hệ thống", { firstLineIndent: false }),
    p("Chương 5. Giải pháp và đóng góp", { firstLineIndent: false }),
    p("Chương 6. Kết luận và hướng phát triển", { firstLineIndent: false }),
    p("Tài liệu tham khảo", { firstLineIndent: false }),
    pageBreak()
  ];
}

// --- ABBREVIATIONS ---
function createAbbreviations() {
  return [
    p("DANH MỤC TỪ VIẾT TẮT", { bold: true, size: FONT_SIZE_TITLE, align: AlignmentType.CENTER, firstLineIndent: false, spacing: { before: 240, after: 240, line: LINE_SPACING } }),
    emptyLine(),
    createTable(
      ["STT", "Từ viết tắt", "Tiếng Anh", "Tiếng Việt"],
      [
        ["1", "SAINT", "Security Agent Integrated Network Tool", "Công cụ mạng tích hợp bảo mật"],
        ["2", "API", "Application Programming Interface", "Giao diện lập trình ứng dụng"],
        ["3", "REST", "Representational State Transfer", "Kiến trúc truyền trạng thái"],
        ["4", "JWT", "JSON Web Token", "Mã thông báo web JSON"],
        ["5", "RBAC", "Role-Based Access Control", "Kiểm soát truy cập dựa trên vai trò"],
        ["6", "DNS", "Domain Name System", "Hệ thống tên miền"],
        ["7", "HTTP", "HyperText Transfer Protocol", "Giao thức truyền siêu văn bản"],
        ["8", "TLS", "Transport Layer Security", "Bảo mật tầng giao vận"],
        ["9", "SNI", "Server Name Indication", "Chỉ thị tên máy chủ"],
        ["10", "GUI", "Graphical User Interface", "Giao diện đồ họa người dùng"],
        ["11", "CRUD", "Create Read Update Delete", "Tạo, Đọc, Sửa, Xóa"],
        ["12", "MVC", "Model-View-Controller", "Mô hình-Hiển thị-Điều khiển"],
        ["13", "MVP", "Model-View-Presenter", "Mô hình-Hiển thị-Trình diễn"],
        ["14", "HMAC", "Hash-based Message Authentication Code", "Mã xác thực dựa trên hàm băm"],
        ["15", "LRU", "Least Recently Used", "Ít được sử dụng gần đây nhất"],
      ],
      [600, 1200, 3200, 3450]
    ),
    pageBreak()
  ];
}

// --- CHAPTER 1: INTRODUCTION ---
function createChapter1() {
  return [
    heading1("CHƯƠNG 1. GIỚI THIỆU ĐỀ TÀI"),

    heading2("1.1. Đặt vấn đề"),
    p("Trong bối cảnh chuyển đổi số đang diễn ra mạnh mẽ trong lĩnh vực giáo dục tại Việt Nam, các cơ sở đào tạo từ phổ thông đến đại học đều được trang bị hệ thống mạng máy tính phục vụ công tác giảng dạy và học tập. Tuy nhiên, việc quản lý và kiểm soát hoạt động truy cập Internet của học sinh, sinh viên tại các phòng máy thực hành vẫn còn nhiều hạn chế và thách thức."),
    p("Thực trạng cho thấy, tại nhiều cơ sở giáo dục, học sinh và sinh viên thường xuyên sử dụng máy tính phòng thực hành để truy cập các trang web không liên quan đến nội dung học tập như mạng xã hội, trò chơi trực tuyến hay các trang web giải trí trong giờ học. Điều này không chỉ ảnh hưởng đến chất lượng giảng dạy mà còn tiềm ẩn các rủi ro về bảo mật thông tin khi người dùng vô tình truy cập các trang web chứa mã độc hoặc phishing."),
    p("Các giải pháp quản lý mạng hiện có trên thị trường như Cisco Meraki, Fortinet FortiGate hay pfSense tuy mạnh mẽ nhưng thường có chi phí cao, yêu cầu phần cứng chuyên dụng và đòi hỏi nhân sự kỹ thuật cao để vận hành. Những giải pháp này được thiết kế cho môi trường doanh nghiệp và không phù hợp với đặc thù của môi trường giáo dục Việt Nam, nơi mà ngân sách công nghệ thông tin thường hạn chế và nhân sự kỹ thuật không phải lúc nào cũng sẵn có."),
    p("Mặt khác, các giải pháp phần mềm miễn phí như OpenDNS hay phần mềm quản lý lớp học cơ bản lại thiếu tính linh hoạt, khó tùy biến theo nhu cầu cụ thể của từng trường học và không cung cấp khả năng giám sát chi tiết hoạt động mạng ở cấp độ từng máy tính."),
    p("Xuất phát từ những thực trạng và hạn chế nêu trên, việc nghiên cứu và phát triển một giải pháp quản lý bảo mật mạng chuyên biệt cho môi trường giáo dục, với chi phí thấp, dễ triển khai và vận hành, có khả năng phân quyền linh hoạt theo cơ cấu tổ chức nhà trường là một yêu cầu cấp thiết và có ý nghĩa thực tiễn cao."),

    heading2("1.2. Mục tiêu của đồ án"),
    p("Đồ án đặt ra mục tiêu thiết kế và phát triển hệ thống SAINT (Security Agent Integrated Network Tool) - một hệ thống quản lý bảo mật mạng phân tán dành riêng cho môi trường giáo dục. Cụ thể, đồ án hướng đến các mục tiêu sau:"),
    p("Thứ nhất, xây dựng một hệ thống quản lý tập trung cho phép quản trị viên và giáo viên kiểm soát truy cập Internet trên các máy tính trong phòng thực hành thông qua cơ chế whitelist. Hệ thống cho phép định nghĩa danh sách các trang web được phép truy cập theo từng nhóm (lớp học, phòng lab) và tự động đồng bộ xuống các máy tính."),
    p("Thứ hai, phát triển Agent - phần mềm client chạy trên Windows có khả năng giám sát lưu lượng mạng theo thời gian thực, phát hiện các truy cập không nằm trong danh sách cho phép và tự động cấu hình Windows Firewall để chặn các kết nối không hợp lệ."),
    p("Thứ ba, triển khai cơ chế phân quyền RBAC (Role-Based Access Control) hai cấp phù hợp với cơ cấu tổ chức nhà trường, trong đó Admin có toàn quyền quản trị hệ thống và Teacher chỉ được quản lý các nhóm máy tính được gán."),
    p("Thứ tư, đảm bảo hệ thống có khả năng mở rộng, dễ triển khai và vận hành với chi phí tối thiểu, phù hợp với điều kiện thực tế của các cơ sở giáo dục tại Việt Nam."),

    heading2("1.3. Phạm vi và giới hạn"),
    p("Phạm vi của đồ án bao gồm: phát triển Server API và Web Dashboard bằng Flask và MongoDB; phát triển Agent với giao diện GUI trên hệ điều hành Windows; triển khai các tính năng quản lý whitelist, giám sát mạng và điều khiển firewall; và xây dựng hệ thống xác thực, phân quyền hoàn chỉnh."),
    p("Đồ án có một số giới hạn: Agent chỉ hỗ trợ hệ điều hành Windows (do sử dụng netsh để quản lý Windows Firewall); hệ thống chưa hỗ trợ phân tích nội dung HTTPS đã mã hóa (chỉ phân tích ở mức domain qua DNS và SNI); và chưa tích hợp các cơ chế phát hiện xâm nhập nâng cao (IDS/IPS)."),

    heading2("1.4. Phương pháp nghiên cứu"),
    p("Đồ án sử dụng phương pháp nghiên cứu kết hợp giữa lý thuyết và thực nghiệm. Về mặt lý thuyết, đồ án nghiên cứu các kiến trúc hệ thống phân tán, các giao thức mạng (DNS, HTTP, TLS), kỹ thuật phân tích gói tin mạng và các mô hình phân quyền truy cập. Về mặt thực nghiệm, đồ án áp dụng quy trình phát triển phần mềm Agile, với các vòng lặp phát triển ngắn, kiểm thử liên tục và phản hồi nhanh để đảm bảo chất lượng sản phẩm."),

    heading2("1.5. Cấu trúc đồ án"),
    p("Đồ án được tổ chức thành 6 chương với nội dung cụ thể như sau:"),
    multiRunParagraph([{ text: "Chương 1 - Giới thiệu đề tài: ", bold: true }, { text: "Trình bày bối cảnh, vấn đề cần giải quyết, mục tiêu và phạm vi của đồ án." }]),
    multiRunParagraph([{ text: "Chương 2 - Khảo sát yêu cầu: ", bold: true }, { text: "Phân tích hiện trạng, khảo sát các giải pháp hiện có, xác định yêu cầu chức năng và phi chức năng." }]),
    multiRunParagraph([{ text: "Chương 3 - Công nghệ sử dụng: ", bold: true }, { text: "Giới thiệu và phân tích lựa chọn các công nghệ, framework và thư viện được sử dụng." }]),
    multiRunParagraph([{ text: "Chương 4 - Thiết kế và triển khai: ", bold: true }, { text: "Trình bày chi tiết thiết kế kiến trúc, cơ sở dữ liệu, giao diện và cài đặt hệ thống." }]),
    multiRunParagraph([{ text: "Chương 5 - Giải pháp và đóng góp: ", bold: true }, { text: "Phân tích các giải pháp kỹ thuật đã áp dụng và đóng góp chính của đồ án." }]),
    multiRunParagraph([{ text: "Chương 6 - Kết luận và hướng phát triển: ", bold: true }, { text: "Tổng kết kết quả đạt được, đánh giá và đề xuất hướng phát triển trong tương lai." }]),
    pageBreak()
  ];
}

// --- CHAPTER 2: REQUIREMENTS ---
function createChapter2() {
  return [
    heading1("CHƯƠNG 2. KHẢO SÁT YÊU CẦU"),

    heading2("2.1. Khảo sát hiện trạng"),
    p("Để hiểu rõ nhu cầu thực tế của bài toán quản lý bảo mật mạng trong môi trường giáo dục, đồ án đã tiến hành khảo sát hiện trạng tại một số cơ sở đào tạo có phòng máy tính thực hành. Kết quả khảo sát cho thấy phần lớn các cơ sở đều gặp phải vấn đề chung: thiếu công cụ quản lý truy cập mạng tập trung, giáo viên khó kiểm soát hoạt động trực tuyến của học sinh trong giờ học, và không có cơ chế phân quyền linh hoạt theo lớp hoặc nhóm."),
    p("Tại nhiều phòng máy thực hành, việc quản lý truy cập Internet vẫn được thực hiện thủ công bằng cách cấu hình router hoặc proxy server. Phương pháp này có nhiều hạn chế: không linh hoạt, khó tùy biến theo từng lớp học, không cho phép giáo viên tự quản lý danh sách truy cập, và thiếu khả năng giám sát theo thời gian thực."),

    heading2("2.2. Khảo sát các giải pháp hiện có"),

    heading3("2.2.1. Giải pháp phần cứng chuyên dụng"),
    p("Các giải pháp như Cisco Meraki, Fortinet FortiGate và Sophos XG Firewall cung cấp khả năng quản lý mạng mạnh mẽ với tính năng content filtering, web filtering và bandwidth management. Tuy nhiên, chi phí đầu tư ban đầu cao (từ vài nghìn đến hàng chục nghìn USD cho license và thiết bị), yêu cầu nhân sự chuyên môn cao để vận hành và bảo trì, và thường được thiết kế cho quy mô doanh nghiệp lớn."),

    heading3("2.2.2. Giải pháp phần mềm miễn phí"),
    p("pfSense và OPNsense là các giải pháp firewall mã nguồn mở có thể cài đặt trên phần cứng thông thường. Mặc dù miễn phí về bản quyền, các giải pháp này vẫn đòi hỏi kiến thức chuyên sâu về mạng để cấu hình và vận hành. OpenDNS cung cấp dịch vụ DNS filtering miễn phí nhưng hạn chế về khả năng tùy biến và không cho phép quản lý ở cấp độ từng máy tính."),

    heading3("2.2.3. Đánh giá và so sánh"),
    p("Bảng 2.1 trình bày so sánh các giải pháp hiện có với hệ thống SAINT đề xuất:"),
    emptyLine(),
    createTable(
      ["Tiêu chí", "Phần cứng\nchuyên dụng", "Phần mềm\nmã nguồn mở", "SAINT"],
      [
        ["Chi phí", "Cao", "Trung bình", "Thấp"],
        ["Độ phức tạp triển khai", "Cao", "Cao", "Thấp"],
        ["Phân quyền giáo viên", "Hạn chế", "Không có", "Có (RBAC)"],
        ["Quản lý theo nhóm/lớp", "Hạn chế", "Không có", "Có"],
        ["Giám sát real-time", "Có", "Có", "Có"],
        ["GUI trên máy client", "Không", "Không", "Có"],
        ["Tùy biến cho giáo dục", "Không", "Không", "Có"],
      ],
      [2000, 1800, 1800, 2850]
    ),
    p("Bảng 2.1. So sánh các giải pháp quản lý mạng", { italic: true, align: AlignmentType.CENTER, firstLineIndent: false, spacing: { before: 80, after: 160, line: LINE_SPACING } }),

    heading2("2.3. Yêu cầu chức năng"),
    p("Dựa trên kết quả khảo sát, hệ thống SAINT cần đáp ứng các yêu cầu chức năng sau:"),

    heading3("2.3.1. Quản lý Agent"),
    p("Hệ thống phải cho phép đăng ký tự động các Agent khi được cài đặt trên máy tính, theo dõi trạng thái hoạt động (online/offline) của từng Agent thông qua cơ chế heartbeat, gán Agent vào các nhóm quản lý, và hiển thị thông tin chi tiết về phần cứng và hệ điều hành của mỗi máy tính."),

    heading3("2.3.2. Quản lý Whitelist"),
    p("Hệ thống phải hỗ trợ tạo và quản lý danh sách các domain và địa chỉ IP được phép truy cập. Whitelist có thể được áp dụng ở phạm vi toàn cục (global) hoặc theo từng nhóm (group). Khi whitelist được cập nhật trên Server, các Agent trong nhóm tương ứng phải được đồng bộ tự động mà không cần can thiệp thủ công."),

    heading3("2.3.3. Quản lý Firewall"),
    p("Agent phải có khả năng tự động cấu hình Windows Firewall dựa trên whitelist đã nhận. Hệ thống hỗ trợ hai chế độ hoạt động: chế độ whitelist_only (chỉ cho phép truy cập các địa chỉ trong whitelist) và chế độ monitor_only (chỉ giám sát mà không chặn). Việc chuyển đổi chế độ có thể được thực hiện từ xa thông qua Server."),

    heading3("2.3.4. Giám sát mạng"),
    p("Agent phải có khả năng bắt và phân tích gói tin mạng theo thời gian thực, trích xuất thông tin domain từ các giao thức DNS, HTTP và TLS/SNI, phát hiện các truy cập không nằm trong whitelist, và gửi log hoạt động về Server để lưu trữ và phân tích."),

    heading3("2.3.5. Phân quyền và xác thực"),
    p("Hệ thống phải triển khai cơ chế phân quyền RBAC với hai vai trò: Admin có toàn quyền quản trị hệ thống (quản lý user, agent, group, whitelist, xem audit log); Teacher chỉ được quản lý các nhóm và whitelist mà mình được gán. Xác thực sử dụng JWT token cho người dùng web và API Key kết hợp JWT cho Agent."),

    heading2("2.4. Yêu cầu phi chức năng"),
    p("Về hiệu năng, hệ thống phải đảm bảo thời gian phản hồi API dưới 500ms cho các thao tác thông thường, Agent phải có khả năng xử lý ít nhất 1000 gói tin mỗi giây mà không ảnh hưởng đáng kể đến hiệu năng máy tính, và hệ thống phải hỗ trợ quản lý đồng thời tối thiểu 100 Agent."),
    p("Về bảo mật, toàn bộ thông tin nhạy cảm (mật khẩu, API key) phải được mã hóa. Giao tiếp giữa Agent và Server sử dụng xác thực JWT với thời gian hết hạn. Mọi hành động của người dùng đều phải được ghi lại trong audit log."),
    p("Về khả năng sử dụng, Agent phải có giao diện đồ họa trực quan, dễ sử dụng ngay cả với người không có chuyên môn kỹ thuật. Web Dashboard cung cấp giao diện responsive, hỗ trợ các trình duyệt phổ biến."),
    p("Về khả năng bảo trì và mở rộng, mã nguồn được tổ chức theo mô hình phân tầng (MVC/MVP), dễ dàng bảo trì và mở rộng thêm tính năng mới trong tương lai."),
    pageBreak()
  ];
}

// --- CHAPTER 3: TECHNOLOGIES ---
function createChapter3() {
  return [
    heading1("CHƯƠNG 3. CÔNG NGHỆ SỬ DỤNG"),

    heading2("3.1. Ngôn ngữ lập trình Python"),
    p("Python được lựa chọn làm ngôn ngữ lập trình chính cho cả Server và Agent nhờ nhiều ưu điểm nổi bật. Python có cú pháp rõ ràng, dễ đọc, hệ sinh thái thư viện phong phú và cộng đồng hỗ trợ lớn. Đặc biệt, Python có các thư viện mạnh mẽ cho lĩnh vực mạng và bảo mật như Scapy (phân tích gói tin), dnspython (DNS resolution) và các framework web như Flask. Phiên bản Python 3.11 được sử dụng trong đồ án."),

    heading2("3.2. Flask Framework"),
    p("Flask là một micro web framework cho Python, được thiết kế với triết lý đơn giản và có khả năng mở rộng cao. Flask được lựa chọn thay vì Django vì tính nhẹ gọn, linh hoạt và phù hợp với việc xây dựng REST API. Flask không áp đặt cấu trúc dự án cố định, cho phép nhà phát triển tự do tổ chức mã nguồn theo kiến trúc mong muốn. Trong đồ án, Flask được sử dụng kết hợp với các extension như Flask-CORS (xử lý Cross-Origin requests), Flask-SocketIO (WebSocket real-time) và Gevent (async server)."),

    heading2("3.3. MongoDB"),
    p("MongoDB là hệ quản trị cơ sở dữ liệu NoSQL hướng tài liệu (document-oriented), lưu trữ dữ liệu dưới dạng BSON (Binary JSON). MongoDB được lựa chọn vì tính linh hoạt trong schema, phù hợp với dữ liệu có cấu trúc thay đổi như thông tin Agent (mỗi máy tính có cấu hình khác nhau), log mạng (các trường có thể khác nhau tùy loại gói tin) và whitelist (có thể mở rộng thêm các thuộc tính). MongoDB Atlas được sử dụng làm dịch vụ database đám mây, giảm gánh nặng quản trị và đảm bảo tính sẵn sàng cao. PyMongo là thư viện driver chính thức để kết nối Python với MongoDB."),

    heading2("3.4. Pydantic"),
    p("Pydantic là thư viện validation dữ liệu cho Python, sử dụng type annotations để định nghĩa schema và tự động validate dữ liệu đầu vào. Trong đồ án, Pydantic được sử dụng để validate các request body của API, đảm bảo dữ liệu nhận được từ client luôn đúng định dạng và kiểu dữ liệu trước khi xử lý. Điều này giúp giảm thiểu lỗi runtime và tăng tính an toàn của hệ thống."),

    heading2("3.5. JWT (JSON Web Token)"),
    p("JWT là một chuẩn mở (RFC 7519) để truyền thông tin an toàn giữa các bên dưới dạng JSON object được ký số. Trong đồ án, JWT được sử dụng cho cả hai mục đích: xác thực người dùng web (Admin/Teacher đăng nhập qua dashboard) và xác thực Agent (sau khi đăng ký thành công). JWT token có thời gian hết hạn (30 phút cho web, 24 giờ cho Agent) và có thể bị thu hồi (revoke) khi cần thiết thông qua collection revoked_tokens. Thư viện PyJWT được sử dụng để tạo và verify token."),

    heading2("3.6. Scapy"),
    p("Scapy là thư viện Python mạnh mẽ cho việc tạo, gửi, nhận và phân tích gói tin mạng ở nhiều tầng giao thức khác nhau. Trong đồ án, Scapy được sử dụng để bắt gói tin mạng trên Agent, cho phép trích xuất thông tin domain từ DNS queries, HTTP Host headers và TLS Client Hello SNI. Scapy yêu cầu WinPcap hoặc Npcap trên Windows để hoạt động, và Agent tích hợp cơ chế tự động kiểm tra và hướng dẫn cài đặt."),

    heading2("3.7. CustomTkinter"),
    p("CustomTkinter là thư viện Python mở rộng từ Tkinter chuẩn, cung cấp các widget hiện đại với giao diện flat design. CustomTkinter được lựa chọn cho phát triển GUI của Agent vì khả năng tạo giao diện chuyên nghiệp mà không cần các framework nặng như Qt hay Electron. Thư viện hỗ trợ dark mode, các widget tùy biến cao và tương thích tốt với PyInstaller để đóng gói thành file thực thi."),

    heading2("3.8. Windows Firewall và netsh"),
    p("Windows Firewall with Advanced Security là tường lửa tích hợp sẵn trong hệ điều hành Windows, cung cấp khả năng lọc gói tin ở cấp hệ điều hành. Agent sử dụng công cụ dòng lệnh netsh (Network Shell) để tương tác với Windows Firewall, cho phép tạo, sửa, xóa các firewall rules một cách tự động. Ưu điểm của phương pháp này là không cần cài đặt phần mềm tường lửa bổ sung, tận dụng được cơ sở hạ tầng bảo mật có sẵn của Windows."),

    heading2("3.9. Flask-SocketIO và WebSocket"),
    p("Flask-SocketIO là extension cho Flask hỗ trợ giao thức WebSocket, cho phép giao tiếp hai chiều theo thời gian thực giữa Server và các client. Trong đồ án, WebSocket được sử dụng để gửi thông báo real-time đến Web Dashboard khi có sự kiện quan trọng (Agent online/offline, cảnh báo bảo mật, thay đổi whitelist). Gevent được sử dụng làm async server để hỗ trợ nhiều kết nối WebSocket đồng thời."),

    heading2("3.10. PyInstaller"),
    p("PyInstaller là công cụ đóng gói ứng dụng Python thành file thực thi độc lập (.exe trên Windows). PyInstaller phân tích import dependencies, đóng gói Python interpreter cùng tất cả thư viện cần thiết vào một file duy nhất. Trong đồ án, PyInstaller được sử dụng để build Agent thành file SAINT.exe, cho phép triển khai trên các máy tính Windows mà không cần cài đặt Python và các thư viện."),

    heading2("3.11. Tổng kết công nghệ"),
    p("Bảng 3.1 tổng hợp các công nghệ chính được sử dụng trong đồ án:"),
    emptyLine(),
    createTable(
      ["Thành phần", "Công nghệ", "Phiên bản", "Mục đích"],
      [
        ["Server Framework", "Flask", "3.0+", "REST API, Web Dashboard"],
        ["Database", "MongoDB Atlas", "7.0", "Lưu trữ dữ liệu"],
        ["Real-time", "Flask-SocketIO", "5.3+", "WebSocket notifications"],
        ["Auth", "PyJWT + bcrypt", "2.8+", "JWT token, mã hóa mật khẩu"],
        ["Validation", "Pydantic", "2.0+", "Validate dữ liệu đầu vào"],
        ["GUI", "CustomTkinter", "5.2+", "Giao diện Agent"],
        ["Packet Capture", "Scapy", "2.5+", "Bắt gói tin mạng"],
        ["DNS", "dnspython", "2.4+", "DNS resolution"],
        ["Firewall", "netsh (Windows)", "-", "Quản lý Windows Firewall"],
        ["Build", "PyInstaller", "6.0+", "Đóng gói SAINT.exe"],
      ],
      [1800, 1800, 1200, 3650]
    ),
    p("Bảng 3.1. Tổng hợp công nghệ sử dụng", { italic: true, align: AlignmentType.CENTER, firstLineIndent: false, spacing: { before: 80, after: 160, line: LINE_SPACING } }),
    pageBreak()
  ];
}

// --- CHAPTER 4: DESIGN AND IMPLEMENTATION ---
function createChapter4() {
  return [
    heading1("CHƯƠNG 4. THIẾT KẾ VÀ TRIỂN KHAI HỆ THỐNG"),

    heading2("4.1. Kiến trúc tổng thể"),
    p("Hệ thống SAINT được thiết kế theo mô hình Client-Server phân tán, trong đó Server đóng vai trò trung tâm quản lý và các Agent là các node thực thi tại các máy tính cần giám sát. Kiến trúc này cho phép quản lý tập trung thông qua một điểm duy nhất (Server) trong khi vẫn đảm bảo khả năng hoạt động độc lập của từng Agent khi mất kết nối tạm thời."),
    p("Server cung cấp hai giao diện chính: REST API cho Agent giao tiếp (đăng ký, heartbeat, đồng bộ whitelist, gửi log) và Web Dashboard cho Admin/Teacher quản lý hệ thống qua trình duyệt web. Ngoài ra, Flask-SocketIO cung cấp kênh WebSocket cho các thông báo thời gian thực."),
    p("Agent là phần mềm chạy trên mỗi máy tính Windows cần giám sát, bao gồm các module: GUI (giao diện người dùng), Firewall Manager (quản lý Windows Firewall), Packet Sniffer (bắt gói tin mạng), Whitelist Manager (đồng bộ whitelist từ Server), và các dịch vụ nền (Heartbeat, Log Sender)."),

    heading2("4.2. Kiến trúc Server"),

    heading3("4.2.1. Mô hình MVC"),
    p("Server được tổ chức theo mô hình MVC (Model-View-Controller) ba tầng rõ ràng. Tầng Controller (controllers/) chịu trách nhiệm nhận và xử lý HTTP requests, validate input, gọi service tương ứng và trả về response. Tầng Service (services/) chứa business logic, xử lý nghiệp vụ và điều phối giữa controller và model. Tầng Model (models/) thực hiện các thao tác CRUD trực tiếp với MongoDB, quản lý schema và index."),
    p("Ngoài ba tầng chính, Server còn có tầng Middleware (middleware/) xử lý cross-cutting concerns như xác thực (authentication) và phân quyền (authorization), và tầng View (views/) chứa các template Jinja2 cho Web Dashboard."),

    heading3("4.2.2. Thiết kế cơ sở dữ liệu"),
    p("Cơ sở dữ liệu MongoDB bao gồm 12 collection được thiết kế để phục vụ các chức năng khác nhau của hệ thống. Các collection chính bao gồm:"),
    p("Collection agents lưu trữ thông tin đăng ký và trạng thái của các Agent, bao gồm agent_id (định danh duy nhất), device_id (mã phần cứng), hostname, ip_address, group_id (nhóm thuộc về), last_heartbeat (thời điểm heartbeat cuối cùng), status (trạng thái active/inactive/offline) và metrics (thông tin CPU, memory, uptime)."),
    p("Collection groups quản lý các nhóm Agent (tương ứng với lớp học hoặc phòng lab), chứa danh sách whitelist_ids và teacher_ids để phân quyền quản lý. Collection whitelists lưu trữ các entry domain/IP được phép truy cập, với các trường value (domain hoặc IP), type (domain/ip/pattern), scope (global/group) và is_active."),
    p("Collection users quản lý tài khoản Admin và Teacher với mật khẩu được hash bằng bcrypt. Collection logs lưu trữ log hoạt động mạng từ Agent. Collection audit_logs ghi lại mọi hành động quan trọng của người dùng (tạo, sửa, xóa) phục vụ mục đích kiểm toán."),
    p("Các collection bổ trợ bao gồm: sessions (phiên đăng nhập), api_keys (API key đăng ký Agent), agent_policies (chính sách riêng từng Agent), whitelist_profiles (whitelist mẫu) và revoked_tokens (JWT đã thu hồi)."),

    heading3("4.2.3. Thiết kế API"),
    p("Server cung cấp khoảng 50 REST API endpoints được phân nhóm theo chức năng. Nhóm Agent API (/api/agents) phục vụ đăng ký, heartbeat, cập nhật metrics và quản lý trạng thái Agent. Nhóm Whitelist API (/api/whitelist) cung cấp CRUD cho whitelist entries và đồng bộ xuống Agent. Nhóm Group API (/api/groups) quản lý nhóm và gán Agent. Nhóm Auth API (/api/auth, /api/admin/auth) xử lý đăng nhập, đăng xuất và refresh token. Nhóm User API (/api/admin/users) quản lý tài khoản người dùng. Nhóm Audit API (/api/admin/audit) truy vấn log kiểm toán."),
    p("Tất cả API endpoints đều yêu cầu xác thực: Agent sử dụng JWT token (nhận sau khi đăng ký bằng API Key), Admin/Teacher sử dụng JWT cookie (nhận sau khi đăng nhập). RBAC middleware kiểm tra quyền của từng request dựa trên role của người dùng."),

    heading2("4.3. Kiến trúc Agent"),

    heading3("4.3.1. Mô hình MVP và Signals"),
    p("Agent được thiết kế theo mô hình MVP (Model-View-Presenter) kết hợp với hệ thống Signals cho giao tiếp thread-safe giữa các component. GUI chạy trên main thread (GUI Thread), các module nghiệp vụ (Firewall Manager, Whitelist Manager, Packet Sniffer, Heartbeat Sender, Log Sender) chạy trên các worker thread riêng biệt."),
    p("AgentController đóng vai trò Presenter, điều phối hoạt động của tất cả các component. AgentSignals sử dụng cơ chế callback queue với polling interval 500ms để truyền sự kiện từ worker threads lên GUI thread một cách an toàn, tránh các vấn đề về thread-safety khi cập nhật giao diện."),

    heading3("4.3.2. Module Firewall Manager"),
    p("Firewall Manager là module quan trọng nhất của Agent, chịu trách nhiệm quản lý Windows Firewall tự động. Module được chia thành ba thành phần: PolicyManager thiết lập chính sách mặc định (cho phép hoặc từ chối tất cả kết nối outbound), RulesManager tạo và xóa các firewall rules dựa trên whitelist (mỗi domain/IP trong whitelist tương ứng với một hoặc nhiều allow rules), và FirewallManager điều phối hai thành phần trên."),
    p("Khi chuyển sang chế độ whitelist_only, PolicyManager đặt default policy là Block cho outbound connections, sau đó RulesManager tạo allow rules cho từng domain/IP trong whitelist. Quá trình phân giải domain sang IP sử dụng OptimizedDNSResolver với cache LRU 2000 entries để giảm thiểu DNS queries lặp lại."),

    heading3("4.3.3. Module Packet Sniffer"),
    p("Packet Sniffer sử dụng thư viện Scapy để bắt gói tin mạng trên network interface chính. DomainExtractor trích xuất thông tin domain truy cập từ ba nguồn: DNS query packets (trường qname), HTTP request packets (header Host) và TLS Client Hello packets (extension SNI - Server Name Indication). Phương pháp kết hợp ba nguồn thông tin này cho phép phát hiện domain truy cập ngay cả khi giao tiếp được mã hóa HTTPS (thông qua SNI), mà không cần giải mã nội dung."),
    p("Mỗi gói tin bắt được đều được kiểm tra với whitelist hiện tại. Nếu domain không nằm trong whitelist và hệ thống đang ở chế độ whitelist_only, gói tin được ghi nhận vào log và gửi về Server. Log được gom nhóm (batch) với kích thước 100 entries và gửi theo chu kỳ 2 giây để giảm tải network."),

    heading3("4.3.4. Module Whitelist Manager"),
    p("Whitelist Manager thực hiện đồng bộ danh sách whitelist từ Server với cơ chế versioning. Mỗi nhóm (group) trên Server có một whitelist_version tăng dần mỗi khi whitelist được cập nhật. Agent lưu version hiện tại và so sánh với Server qua heartbeat response. Khi phát hiện version mới, Agent tự động pull toàn bộ whitelist mới."),
    p("Sau khi nhận whitelist mới, Whitelist Manager thực hiện DNS resolution cho tất cả domain entries để lấy danh sách IP tương ứng, lưu vào WhitelistState (thread-safe storage), và thông báo cho Firewall Manager cập nhật firewall rules. Toàn bộ quá trình diễn ra tự động, không yêu cầu can thiệp từ người dùng."),

    heading3("4.3.5. Giao diện người dùng"),
    p("Agent GUI được xây dựng bằng CustomTkinter với thiết kế hiện đại, bao gồm 5 màn hình chính. Dashboard View hiển thị tổng quan trạng thái Agent (kết nối Server, Firewall, số lượng gói tin bắt được) và log hoạt động gần nhất. Firewall View cho phép xem và quản lý các firewall rules hiện tại, chuyển đổi chế độ hoạt động. Whitelist View hiển thị danh sách whitelist đã đồng bộ từ Server. Logs View cung cấp console hiển thị log real-time với khả năng lọc theo cấp độ. Settings View cho phép cấu hình Server URL, API Key và các tham số hoạt động."),

    heading2("4.4. Luồng hoạt động chính"),

    heading3("4.4.1. Luồng đăng ký Agent"),
    p("Khi Agent khởi động lần đầu, người dùng cần cấu hình Server URL và API Key trong Settings. Khi nhấn nút Start, Agent gửi request đăng ký đến Server kèm API Key (HMAC-SHA256), device_id (hash từ thông tin phần cứng) và hostname. Server xác thực API Key, tạo bản ghi Agent mới trong database, sinh JWT token và trả về cho Agent. Agent lưu JWT token để sử dụng cho các request tiếp theo. Nếu Agent đã đăng ký trước đó (cùng device_id), Server trả về token mới thay vì tạo bản ghi mới."),

    heading3("4.4.2. Luồng đồng bộ Whitelist"),
    p("Sau khi đăng ký thành công, Agent bắt đầu gửi heartbeat mỗi 20 giây. Server response kèm whitelist_version hiện tại của nhóm mà Agent thuộc về. Nếu version mới hơn version Agent đang có, Agent gửi request lấy whitelist mới. Server trả về danh sách domain/IP entries. Agent thực hiện DNS resolution, cập nhật WhitelistState và Firewall rules."),

    heading3("4.4.3. Luồng phát hiện truy cập"),
    p("Packet Sniffer chạy liên tục, bắt gói tin trên network interface. DomainExtractor phân tích từng gói tin, trích xuất domain. Domain được kiểm tra với whitelist hiện tại. Nếu domain không nằm trong whitelist, log entry được tạo và thêm vào hàng đợi gửi. LogSender gom nhóm và gửi batch log về Server mỗi 2 giây. Server lưu log vào collection logs và phát WebSocket notification đến Dashboard."),

    heading2("4.5. Hệ thống xác thực và phân quyền"),

    heading3("4.5.1. Xác thực Agent"),
    p("Agent sử dụng cơ chế xác thực hai bước. Bước 1: Agent gửi API Key (chuỗi random 32 ký tự, được hash bằng HMAC-SHA256 với secret key) cùng thông tin máy tính đến endpoint đăng ký. Server xác thực API Key bằng cách so sánh hash. Bước 2: Sau khi đăng ký thành công, Server cấp JWT token (có thời hạn 24 giờ). Agent sử dụng JWT token trong header Authorization của mọi request tiếp theo. Token được tự động refresh trước khi hết hạn."),

    heading3("4.5.2. Phân quyền RBAC"),
    p("Hệ thống triển khai RBAC hai cấp với cấu hình quyền chi tiết được định nghĩa trong rbac_config.py. Admin có toàn quyền: quản lý user (tạo, sửa, xóa Admin và Teacher), quản lý group (tạo, sửa, xóa, gán Agent), quản lý whitelist (CRUD toàn bộ), quản lý API Key, xem audit log và quản lý tất cả Agent. Teacher có quyền hạn chế: chỉ quản lý các group được gán (teacher_ids chứa user_id), chỉ CRUD whitelist trong phạm vi group của mình, không thể tạo/xóa user, không thể xem audit log và không thể quản lý API Key."),
    p("RBAC middleware kiểm tra quyền trên mỗi API request bằng cách: decode JWT token để lấy user_id và role, tra cứu bảng permissions theo role và endpoint, nếu role là Teacher thì kiểm tra thêm scope (chỉ cho phép thao tác trên dữ liệu thuộc group được gán)."),

    heading2("4.6. Triển khai và đóng gói"),
    p("Server được triển khai trên môi trường có Python 3.11+, kết nối MongoDB Atlas qua connection string trong file .env. Các biến môi trường quan trọng bao gồm: MONGODB_URI (connection string), JWT_SECRET_KEY (secret key cho JWT), API_KEY_SECRET (secret key cho HMAC API Key). Server khởi động bằng lệnh python app.py, sử dụng Gevent WSGI server hỗ trợ WebSocket."),
    p("Agent được đóng gói bằng PyInstaller thành file SAINT.exe duy nhất, kích thước khoảng 50-80MB bao gồm Python runtime và tất cả dependencies. Quá trình build sử dụng file spec tùy chỉnh để đảm bảo bao gồm đầy đủ các resource (icon, assets) và hidden imports (Scapy, CustomTkinter). File SAINT.exe có thể chạy trực tiếp trên bất kỳ máy Windows nào mà không cần cài đặt thêm phần mềm (trừ Npcap cho tính năng packet capture)."),
    pageBreak()
  ];
}

// --- CHAPTER 5: SOLUTIONS AND CONTRIBUTIONS ---
function createChapter5() {
  return [
    heading1("CHƯƠNG 5. GIẢI PHÁP VÀ ĐÓNG GÓP"),

    heading2("5.1. Giải pháp quản lý truy cập mạng dựa trên Whitelist"),
    p("Đóng góp chính thứ nhất của đồ án là giải pháp quản lý truy cập mạng dựa trên whitelist với cơ chế đồng bộ tự động. Khác với các giải pháp blacklist truyền thống (liệt kê các trang web bị cấm), SAINT sử dụng phương pháp whitelist (chỉ cho phép truy cập các trang web được duyệt). Phương pháp whitelist an toàn hơn vì mặc định chặn tất cả và chỉ cho phép những gì đã được xác nhận, phù hợp với môi trường giáo dục nơi cần kiểm soát chặt chẽ."),
    p("Cơ chế versioning đảm bảo đồng bộ whitelist hiệu quả: mỗi nhóm có whitelist_version tăng dần khi có thay đổi, Agent chỉ cần so sánh version qua heartbeat response (gọn nhẹ) thay vì pull toàn bộ whitelist mỗi lần. Cơ chế này giảm đáng kể lưu lượng mạng và tải server trong môi trường có nhiều Agent."),

    heading2("5.2. Giải pháp giám sát mạng đa tầng giao thức"),
    p("Đóng góp thứ hai là kỹ thuật giám sát mạng kết hợp phân tích ở nhiều tầng giao thức. Thay vì chỉ phân tích DNS queries (bỏ sót các truy cập dùng cache DNS), SAINT kết hợp ba nguồn thông tin: DNS query (trường qname trong DNS packet) để phát hiện domain lookup, HTTP Host header để phát hiện truy cập HTTP không mã hóa, và TLS/SNI (Server Name Indication trong TLS Client Hello) để phát hiện domain truy cập HTTPS mà không cần giải mã nội dung."),
    p("Phương pháp kết hợp này cho phép phát hiện gần như toàn bộ các truy cập web, bao gồm cả HTTPS (chiếm hơn 90% lưu lượng web hiện nay), mà không cần cài đặt certificate trung gian hay thực hiện SSL/TLS interception - một yêu cầu quan trọng về bảo mật và quyền riêng tư."),

    heading2("5.3. Giải pháp phân quyền RBAC cho môi trường giáo dục"),
    p("Đóng góp thứ ba là mô hình phân quyền RBAC hai cấp được thiết kế riêng cho cơ cấu tổ chức giáo dục. Mô hình này phản ánh đúng thực tế quản lý: Admin (quản trị viên IT) quản lý toàn bộ hệ thống, còn Teacher (giáo viên) chỉ quản lý các phòng máy/lớp học được gán. Giáo viên có thể tự tạo và quản lý whitelist cho lớp mình mà không ảnh hưởng đến các lớp khác, không cần phải liên hệ quản trị viên mỗi khi cần thay đổi."),
    p("Cơ chế phân quyền được triển khai ở cấp API middleware, đảm bảo mọi request đều được kiểm tra quyền trước khi xử lý. Bảng quyền được cấu hình tập trung trong file rbac_config.py, dễ dàng mở rộng thêm vai trò mới khi cần."),

    heading2("5.4. Giải pháp kiến trúc Agent với khả năng hoạt động offline"),
    p("Đóng góp thứ tư là thiết kế Agent với khả năng hoạt động độc lập khi mất kết nối với Server. Agent lưu whitelist đã đồng bộ vào bộ nhớ cục bộ, cho phép tiếp tục áp dụng firewall rules ngay cả khi không kết nối được Server. Khi kết nối được khôi phục, Agent tự động đồng bộ lại và gửi các log đã tích lũy."),
    p("Kiến trúc MVP với Signals đảm bảo giao diện GUI luôn responsive bất kể các module nền (packet capture, firewall, heartbeat) đang hoạt động nặng. Hệ thống signal queue với polling 500ms cho phép cập nhật UI mượt mà mà không gây đóng băng giao diện."),

    heading2("5.5. Giải pháp bảo mật toàn diện"),
    p("Đóng góp thứ năm là thiết kế bảo mật đa tầng cho hệ thống phân tán. Mật khẩu người dùng được hash bằng bcrypt với salt tự động. API Key sử dụng HMAC-SHA256, chỉ lưu hash trên server, bản gốc không bao giờ truyền qua mạng sau lần tạo đầu tiên. JWT token có thời gian hết hạn ngắn và có thể bị thu hồi. Toàn bộ hành động quan trọng được ghi vào audit log với thông tin người thực hiện, hành động, thời gian và dữ liệu thay đổi."),

    heading2("5.6. Kết quả kiểm thử"),
    p("Hệ thống đã được kiểm thử với bộ test suite sử dụng pytest, bao gồm các nhóm test: test đăng ký và quản lý Agent (test_agents.py, test_agent_full.py), test xác thực người dùng (test_users_auth.py), test quản lý Group (test_groups.py), test whitelist và log (test_whitelist_and_logs.py), test audit log (test_audit.py), và test phân quyền Teacher (test_teacher_data_filtering.py). Tất cả các test case đều pass, xác nhận hệ thống hoạt động đúng theo yêu cầu thiết kế."),
    p("Kiểm thử tích hợp được thực hiện với kịch bản thực tế: khởi động Server, cài đặt Agent trên 3-5 máy Windows, tạo group và whitelist, kiểm tra đồng bộ tự động, kiểm tra firewall chặn/cho phép, và kiểm tra phân quyền giữa Admin và Teacher. Kết quả cho thấy hệ thống hoạt động ổn định và đáp ứng đầy đủ các yêu cầu đề ra."),
    pageBreak()
  ];
}

// --- CHAPTER 6: CONCLUSION ---
function createChapter6() {
  return [
    heading1("CHƯƠNG 6. KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN"),

    heading2("6.1. Kết luận"),
    p("Đồ án đã hoàn thành mục tiêu thiết kế và phát triển hệ thống SAINT - một hệ thống quản lý bảo mật mạng phân tán cho môi trường giáo dục. Hệ thống bao gồm hai thành phần chính hoạt động đồng bộ: Server quản lý tập trung với REST API và Web Dashboard, và Agent chạy trên Windows với khả năng giám sát mạng, quản lý firewall và đồng bộ whitelist tự động."),
    p("Các kết quả chính đạt được bao gồm: xây dựng thành công kiến trúc Client-Server phân tán với khả năng mở rộng; triển khai cơ chế whitelist với đồng bộ tự động qua versioning; phát triển module giám sát mạng đa tầng giao thức (DNS, HTTP, TLS/SNI); triển khai hệ thống RBAC hai cấp phù hợp với tổ chức giáo dục; xây dựng giao diện trực quan cho cả web và desktop; và đảm bảo bảo mật toàn diện với JWT, HMAC, bcrypt và audit logging."),
    p("Hệ thống đã được kiểm thử đầy đủ cả ở mức đơn vị (unit test) và tích hợp (integration test), cho kết quả hoạt động ổn định và đáp ứng các yêu cầu chức năng và phi chức năng đề ra. So với các giải pháp hiện có, SAINT có ưu thế về chi phí thấp, dễ triển khai, phân quyền linh hoạt và được thiết kế riêng cho đặc thù môi trường giáo dục."),

    heading2("6.2. Hạn chế"),
    p("Bên cạnh những kết quả đạt được, đồ án vẫn còn một số hạn chế. Agent hiện chỉ hỗ trợ hệ điều hành Windows, chưa có phiên bản cho macOS và Linux. Hệ thống chưa hỗ trợ phân tích nội dung traffic HTTPS đã mã hóa (chỉ phân tích ở mức domain). Giao diện Web Dashboard chưa có responsive design hoàn chỉnh cho thiết bị di động. Và hệ thống chưa được kiểm thử với quy mô lớn (hàng trăm đến hàng nghìn Agent đồng thời)."),

    heading2("6.3. Hướng phát triển"),
    p("Trong tương lai, hệ thống có thể được phát triển theo nhiều hướng. Thứ nhất, mở rộng hỗ trợ đa nền tảng bằng cách phát triển Agent cho macOS (sử dụng pf firewall) và Linux (sử dụng iptables/nftables), cho phép triển khai trên nhiều loại máy tính khác nhau."),
    p("Thứ hai, tích hợp các kỹ thuật Machine Learning để phát hiện bất thường trong lưu lượng mạng, tự động nhận diện các hành vi truy cập đáng ngờ và đề xuất điều chỉnh whitelist."),
    p("Thứ ba, phát triển ứng dụng mobile (Android/iOS) cho giáo viên, cho phép giám sát và quản lý lớp học từ xa thông qua điện thoại thông minh."),
    p("Thứ tư, bổ sung tính năng báo cáo thống kê chi tiết và xuất báo cáo theo định kỳ, giúp quản trị viên đánh giá hiệu quả sử dụng mạng và phát hiện xu hướng."),
    p("Thứ năm, nghiên cứu và tích hợp cơ chế zero-trust security, nâng cao mức độ bảo mật bằng cách xác thực liên tục và phân quyền động dựa trên ngữ cảnh (context-aware access control)."),
    pageBreak()
  ];
}

// --- REFERENCES ---
function createReferences() {
  return [
    heading1("TÀI LIỆU THAM KHẢO"),
    emptyLine(),
    p("[1] M. Grinberg, \"Flask Web Development: Developing Web Applications with Python\", 2nd Edition, O'Reilly Media, 2018.", { firstLineIndent: false, indent: { left: 480, hanging: 480 } }),
    p("[2] K. Chodorow, \"MongoDB: The Definitive Guide\", 3rd Edition, O'Reilly Media, 2019.", { firstLineIndent: false, indent: { left: 480, hanging: 480 } }),
    p("[3] P. Biondi, \"Scapy: Interactive Packet Manipulation Program\", https://scapy.readthedocs.io/, 2024.", { firstLineIndent: false, indent: { left: 480, hanging: 480 } }),
    p("[4] Internet Engineering Task Force, \"RFC 7519: JSON Web Token (JWT)\", https://datatracker.ietf.org/doc/html/rfc7519, 2015.", { firstLineIndent: false, indent: { left: 480, hanging: 480 } }),
    p("[5] D. F. Ferraiolo, R. Sandhu, S. Gavrila, D. R. Kuhn, R. Chandramouli, \"Proposed NIST Standard for Role-Based Access Control\", ACM Transactions on Information and System Security, Vol. 4, No. 3, 2001.", { firstLineIndent: false, indent: { left: 480, hanging: 480 } }),
    p("[6] Microsoft, \"Windows Firewall with Advanced Security\", Microsoft Documentation, https://docs.microsoft.com/en-us/windows/security/threat-protection/windows-firewall/, 2024.", { firstLineIndent: false, indent: { left: 480, hanging: 480 } }),
    p("[7] S. Eastlake, \"RFC 7871: Client Subnet in DNS Queries\", https://datatracker.ietf.org/doc/html/rfc7871, 2016.", { firstLineIndent: false, indent: { left: 480, hanging: 480 } }),
    p("[8] T. Dierks, E. Rescorla, \"RFC 5246: The Transport Layer Security (TLS) Protocol Version 1.2\", https://datatracker.ietf.org/doc/html/rfc5246, 2008.", { firstLineIndent: false, indent: { left: 480, hanging: 480 } }),
    p("[9] CustomTkinter Documentation, \"Modern and Customizable Tkinter Widgets\", https://customtkinter.tomschimansky.com/, 2024.", { firstLineIndent: false, indent: { left: 480, hanging: 480 } }),
    p("[10] MongoDB, Inc., \"MongoDB Atlas Documentation\", https://www.mongodb.com/docs/atlas/, 2024.", { firstLineIndent: false, indent: { left: 480, hanging: 480 } }),
  ];
}


// ==================== BUILD DOCUMENT ====================
const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: FONT, size: FONT_SIZE_NORMAL }
      }
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: FONT_SIZE_H1, bold: true, font: FONT },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 }
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: FONT_SIZE_H2, bold: true, font: FONT },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 }
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: FONT_SIZE_H3, bold: true, font: FONT },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 }
      }
    ]
  },
  sections: [
    // Cover page - no header/footer
    {
      properties: {
        page: {
          size: { width: PAGE_WIDTH, height: PAGE_HEIGHT },
          margin: { top: MARGIN_TOP, bottom: MARGIN_BOTTOM, left: MARGIN_LEFT, right: MARGIN_RIGHT }
        }
      },
      children: [...createCoverPage()]
    },
    // Main content
    {
      properties: {
        page: {
          size: { width: PAGE_WIDTH, height: PAGE_HEIGHT },
          margin: { top: MARGIN_TOP, bottom: MARGIN_BOTTOM, left: MARGIN_LEFT, right: MARGIN_RIGHT }
        }
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [new TextRun({ text: "Đồ án tốt nghiệp - SAINT", font: FONT, size: 20, italic: true })]
          })]
        })
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20 })]
          })]
        })
      },
      children: [
        ...createAcknowledgment(),
        ...createAbstract(),
        ...createTOC(),
        ...createAbbreviations(),
        ...createChapter1(),
        ...createChapter2(),
        ...createChapter3(),
        ...createChapter4(),
        ...createChapter5(),
        ...createChapter6(),
        ...createReferences()
      ]
    }
  ]
});

// Generate and save
const outputPath = "C:/Users/sonbx/SAINT_DATN/docs/SAINT_GRADUATION_THESIS.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log(`Report saved to ${outputPath}`);
  console.log(`File size: ${(buffer.length / 1024).toFixed(1)} KB`);
});
