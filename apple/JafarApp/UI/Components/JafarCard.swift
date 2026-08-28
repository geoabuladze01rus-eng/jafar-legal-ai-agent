import SwiftUI

struct JafarCard<Content: View>: View {
    let title: String
    @ViewBuilder var content: Content
    var body: some View { VStack(alignment: .leading, spacing: 14) { Text(title.uppercased()).font(.caption.weight(.semibold)).tracking(1.2).foregroundStyle(JafarPalette.secondary); content }.padding(18).background(JafarPalette.panel, in: RoundedRectangle(cornerRadius: 14)).overlay(RoundedRectangle(cornerRadius: 14).stroke(JafarPalette.border)) }
}
