import Foundation
import Vision
import AppKit
// usage: ocr <dir>  -> prints one JSON line per jpg: {"f":name,"t":[[x,y,w,h,conf,"text"],...]}  (normalized, origin top-left)
let dir = CommandLine.arguments[1]
let files = try FileManager.default.contentsOfDirectory(atPath: dir).filter{$0.hasSuffix(".jpg")}.sorted()
for f in files {
    let url = URL(fileURLWithPath: dir + "/" + f)
    guard let img = NSImage(contentsOf: url), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["zh-Hans", "en-US"]
    req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: cg).perform([req])
    var out: [[Any]] = []
    for o in req.results ?? [] {
        guard let c = o.topCandidates(1).first else { continue }
        let b = o.boundingBox
        out.append([b.minX, 1 - b.maxY, b.width, b.height, c.confidence, c.string])
    }
    let d = try JSONSerialization.data(withJSONObject: ["f": f, "t": out])
    print(String(data: d, encoding: .utf8)!)
    fflush(stdout)
}
