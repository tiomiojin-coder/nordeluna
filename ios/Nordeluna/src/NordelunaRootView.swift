import SwiftUI

struct NordelunaRootView: View {
    @StateObject private var engine = NordelunaEngine.shared

    var body: some View {
        ZStack {
            if engine.phase == .playing || engine.phase == .paused {
                Color.clear.ignoresSafeArea()
            } else {
                loadingBackground
            }

            if engine.phase == .playing {
                if engine.controlsVisible {
                    TouchControlsView()
                        .transition(.opacity)
                } else {
                    VStack {
                        HStack {
                            Spacer()
                            Button {
                                engine.controlsVisible = true
                            } label: {
                                Image(systemName: "gamecontroller.fill")
                                    .frame(width: 48, height: 48)
                                    .background(.ultraThinMaterial, in: Circle())
                            }
                            .foregroundStyle(.white)
                        }
                        Spacer()
                    }
                    .padding()
                }
            }

            if engine.phase == .paused {
                pauseOverlay
            }
        }
        .animation(.easeInOut(duration: 0.2), value: engine.phase)
        .task { engine.start() }
        .alert("Nordeluna", isPresented: alertBinding) {
            Button("OK") { engine.dismissAlert() }
        } message: {
            Text(engine.alertMessage ?? "")
        }
    }

    private var alertBinding: Binding<Bool> {
        Binding(
            get: { engine.alertMessage != nil },
            set: { if !$0 { engine.dismissAlert() } }
        )
    }

    private var loadingBackground: some View {
        ZStack {
            LinearGradient(
                colors: [Color(red: 0.02, green: 0.05, blue: 0.18), Color(red: 0.08, green: 0.2, blue: 0.38)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            VStack(spacing: 22) {
                Image(systemName: "moon.stars.fill")
                    .font(.system(size: 72))
                    .foregroundStyle(.cyan, .white)
                Text("NORDELUNA")
                    .font(.system(size: 34, weight: .black, design: .rounded))
                    .tracking(4)
                    .foregroundStyle(.white)
                if engine.phase == .preparing || engine.phase == .loading {
                    ProgressView().tint(.white).scaleEffect(1.25)
                }
                Text(engine.statusText)
                    .font(.callout.weight(.medium))
                    .foregroundStyle(.white.opacity(0.8))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
        }
    }

    private var pauseOverlay: some View {
        ZStack {
            Color.black.opacity(0.55).ignoresSafeArea()
            VStack(spacing: 18) {
                Text("Jogo pausado")
                    .font(.title.bold())
                    .foregroundStyle(.white)
                Button("Continuar") { engine.resume() }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
            }
            .padding(32)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 24))
        }
    }
}
