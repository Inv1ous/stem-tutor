// Batch literal OCR for the image cleaner: reads image paths (one per line) on stdin, writes one JSON object per line
// {"path": ..., "text": ...} using on-device Apple Vision.  Read-only; used only to recognise exam cover pages.
import Foundation
import ImageIO
import Vision

while let path = readLine() {
    var text = ""
    if let data = FileManager.default.contents(atPath: path),
       let source = CGImageSourceCreateWithData(data as CFData, nil),
       let image = CGImageSourceCreateImageAtIndex(source, 0, nil) {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .fast
        request.recognitionLanguages = ["en-US"]
        request.usesLanguageCorrection = false
        request.usesCPUOnly = true
        try? VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
        text = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
    }
    let line = try! JSONSerialization.data(withJSONObject: ["path": path, "text": text], options: [.sortedKeys])
    FileHandle.standardOutput.write(line + Data("\n".utf8))
}
