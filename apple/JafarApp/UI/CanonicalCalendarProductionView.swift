import SwiftUI

struct CanonicalCalendarProductionView: View {
    @ObservedObject var dashboard: DashboardStore
    let demoMode: Bool
    let matter: DashboardMatter?

    init(dashboard: DashboardStore, demoMode: Bool, matter: DashboardMatter? = nil) {
        self.dashboard = dashboard
        self.demoMode = demoMode
        self.matter = matter
    }

    var body: some View {
        CanonicalCalendarPrototypeView(
            presentation: CalendarPresentationAdapter.make(
                snapshot: dashboard.snapshot,
                demoMode: demoMode,
                matter: matter
            ),
            onRefresh: {
                await dashboard.refresh()
            }
        )
    }
}
