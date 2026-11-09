import Foundation
import PDFKit
import Vision
import AppKit

let pdfPath = "/Users/mac/Downloads/monmenu2025.pdf"
let outDir = "/Users/mac/Kaayfi/monmenu-extraction/ocr"

guard let doc = PDFDocument(url: URL(fileURLWithPath: pdfPath)) else {
    fputs("cannot open pdf\n", stderr)
    exit(1)
}

let args = CommandLine.arguments.dropFirst()
let pages: [Int]
if args.isEmpty {
    pages = Array(0..<doc.pageCount)
} else {
    pages = args.compactMap { Int($0) }.map { $0 - 1 }
}

let scale: CGFloat = 2.4

func render(_ page: PDFPage) -> CGImage? {
    let bounds = page.bounds(for: .mediaBox)
    let w = Int(bounds.width * scale)
    let h = Int(bounds.height * scale)
    guard let cs = CGColorSpace(name: CGColorSpace.sRGB),
          let ctx = CGContext(
            data: nil, width: w, height: h,
            bitsPerComponent: 8, bytesPerRow: 0, space: cs,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
          ) else { return nil }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.saveGState()
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    ctx.restoreGState()
    return ctx.makeImage()
}

let lock = NSLock()

func ocr(pageIndex: Int) {
    let outURL = URL(fileURLWithPath: outDir).appendingPathComponent(String(format: "page_%03d.json", pageIndex + 1))
    if FileManager.default.fileExists(atPath: outURL.path) {
        return
    }
    guard let page = doc.page(at: pageIndex), let cg = render(page) else {
        fputs("render fail \(pageIndex+1)\n", stderr)
        return
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["fr-FR", "en-US"]
    req.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do {
        try handler.perform([req])
    } catch {
        fputs("ocr fail \(pageIndex+1) \(error)\n", stderr)
        return
    }
    let obs = (req.results ?? [])
    var lines: [[String: Any]] = []
    for o in obs {
        guard let c = o.topCandidates(1).first else { continue }
        let b = o.boundingBox
        lines.append([
            "t": c.string,
            "x": Double(b.origin.x),
            "y": Double(b.origin.y),
            "w": Double(b.size.width),
            "h": Double(b.size.height),
            "c": Double(c.confidence),
        ])
    }
    let payload: [String: Any] = ["page": pageIndex + 1, "lines": lines]
    if let data = try? JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys]) {
        try? data.write(to: outURL)
    }
    lock.lock()
    print("done \(pageIndex + 1) lines=\(lines.count)")
    fflush(stdout)
    lock.unlock()
}

let queue = OperationQueue()
queue.maxConcurrentOperationCount = 4
let group = DispatchGroup()
for p in pages {
    group.enter()
    queue.addOperation {
        ocr(pageIndex: p)
        group.leave()
    }
}
group.wait()
print("ALL DONE")
