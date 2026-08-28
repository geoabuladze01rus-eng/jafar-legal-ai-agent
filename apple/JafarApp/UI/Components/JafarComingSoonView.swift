import SwiftUI
struct JafarComingSoonView: View { let title: String; var body: some View { VStack(spacing: 12) { Image(systemName: "hammer").font(.largeTitle).foregroundStyle(.secondary); Text(title).font(.title2.bold()); Text("Раздел готовится").foregroundStyle(.secondary) }.frame(maxWidth: .infinity, maxHeight: .infinity) } }
