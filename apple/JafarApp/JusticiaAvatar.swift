import Foundation
import ImageIO
import SwiftUI
import UniformTypeIdentifiers

enum JusticiaAvatarPhoto {
    static let allowedTypes: [UTType] = [.jpeg, .png, .heic]
    private static let maxFileBytes = 20 * 1024 * 1024
    private static let maxPixels = 80_000_000
    private static let thumbnailSize = 384

    enum ImportError: LocalizedError {
        case tooLarge
        case unreadable

        var errorDescription: String? {
            switch self {
            case .tooLarge: "Фото слишком большое. Выберите файл до 20 МБ и 80 мегапикселей."
            case .unreadable: "Не удалось открыть фото. Выберите изображение JPEG, PNG или HEIC."
            }
        }
    }

    static func importPhoto(from url: URL) throws -> Data {
        let hasAccess = url.startAccessingSecurityScopedResource()
        defer { if hasAccess { url.stopAccessingSecurityScopedResource() } }

        let file = try FileHandle(forReadingFrom: url)
        defer { try? file.close() }
        guard let original = try file.read(upToCount: maxFileBytes + 1), !original.isEmpty else {
            throw ImportError.unreadable
        }
        guard original.count <= maxFileBytes else { throw ImportError.tooLarge }

        let sourceOptions = [kCGImageSourceShouldCache: false] as CFDictionary
        guard
            let source = CGImageSourceCreateWithData(original as CFData, sourceOptions),
            let identifier = CGImageSourceGetType(source),
            let type = UTType(identifier as String),
            allowedTypes.contains(where: { type.conforms(to: $0) }),
            let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, sourceOptions) as? [CFString: Any],
            let width = properties[kCGImagePropertyPixelWidth] as? Int,
            let height = properties[kCGImagePropertyPixelHeight] as? Int,
            width > 0, height > 0
        else { throw ImportError.unreadable }
        guard width <= maxPixels / height else { throw ImportError.tooLarge }

        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: thumbnailSize
        ]
        guard let image = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) else {
            throw ImportError.unreadable
        }
        let data = NSMutableData()
        guard let output = CGImageDestinationCreateWithData(data as CFMutableData, UTType.jpeg.identifier as CFString, 1, nil) else {
            throw ImportError.unreadable
        }
        // Encode the thumbnail pixels only. Do not retain the original file or its metadata.
        CGImageDestinationAddImage(output, image, [kCGImageDestinationLossyCompressionQuality: 0.86] as CFDictionary)
        guard CGImageDestinationFinalize(output) else { throw ImportError.unreadable }
        return data as Data
    }
}

struct JusticiaAvatar: View {
    let data: Data
    let size: CGFloat

    var body: some View {
        Group {
            if !data.isEmpty,
               let source = CGImageSourceCreateWithData(data as CFData, nil),
               let image = CGImageSourceCreateImageAtIndex(source, 0, nil) {
                Image(decorative: image, scale: 1)
                    .resizable()
                    .scaledToFill()
            } else {
                Circle()
                    .fill(JusticiaTheme.blueSoft)
                    .overlay {
                        Image(systemName: "person.fill")
                            .font(.system(size: size * 0.38, weight: .medium))
                            .foregroundStyle(JusticiaTheme.blue)
                    }
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .accessibilityHidden(true)
    }
}
