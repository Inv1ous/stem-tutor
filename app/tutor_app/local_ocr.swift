import Foundation
import ImageIO
import Vision

enum OCRFailure: Error { case unreadableImage }

do {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard !data.isEmpty,
          let source = CGImageSourceCreateWithData(data as CFData, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw OCRFailure.unreadableImage
    }
    let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any]
    let rawOrientation = (properties?[kCGImagePropertyOrientation] as? NSNumber)?.uint32Value ?? 1
    let orientation = CGImagePropertyOrientation(rawValue: rawOrientation) ?? .up
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["en-US"]
    request.usesLanguageCorrection = false
    request.usesCPUOnly = true
    request.preferBackgroundProcessing = true
    try VNImageRequestHandler(cgImage: image, orientation: orientation).perform([request])
    let lines: [[String: Any]] = (request.results ?? []).compactMap { observation in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let box = observation.boundingBox
        return ["text": candidate.string, "confidence": Double(candidate.confidence),
                "box": ["x": box.origin.x, "y": box.origin.y,
                        "width": box.width, "height": box.height]]
    }
    let rotated = [5, 6, 7, 8].contains(Int(orientation.rawValue))
    let result: [String: Any] = ["width": rotated ? image.height : image.width,
                               "height": rotated ? image.width : image.height, "lines": lines]
    FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]))
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    FileHandle.standardError.write(Data("The image could not be recognised.\n".utf8))
    exit(1)
}
