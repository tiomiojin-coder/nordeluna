import SwiftUI

struct NordelunaRootView: View {
    @StateObject private var engine = NordelunaEngine.shared
    @State private var editingControls = false

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
        .onChange(of: engine.phase) { _, phase in
            if phase != .paused { editingControls = false }
        }
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
            if editingControls {
                ControlsEditorView {
                    editingControls = false
                }
            } else {
                VStack(spacing: 18) {
                    Text("Jogo pausado")
                        .font(.title.bold())
                        .foregroundStyle(.white)

                    Button {
                        editingControls = true
                    } label: {
                        Label("Editar controles", systemImage: "keyboard")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.large)

                    Button {
                        engine.resume()
                    } label: {
                        Label("Continuar", systemImage: "play.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                }
                .frame(width: 300)
                .padding(32)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 24))
            }
        }
    }
}

private struct ControlsEditorView: View {
    @ObservedObject private var engine = NordelunaEngine.shared
    let onDone: () -> Void

    var body: some View {
        VStack(spacing: 14) {
            HStack {
                Button(action: onDone) {
                    Label("Voltar", systemImage: "chevron.left")
                }
                .buttonStyle(.bordered)

                Spacer()

                Text("Controles")
                    .font(.title2.bold())

                Spacer()

                Button("Padrão") {
                    engine.resetControlMappings()
                }
                .buttonStyle(.bordered)
            }

            Text("Toque na tecla ao lado de cada botão. O direcional usa as quatro setas do teclado.")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            ScrollView {
                VStack(spacing: 10) {
                    ForEach(TouchControlSlot.allCases) { slot in
                        HStack(spacing: 16) {
                            Text(slot.face)
                                .font(.title3.bold())
                                .frame(width: 44, height: 44)
                                .background(.white.opacity(0.12), in: Circle())

                            Text("Botão \(slot.face)")
                                .font(.headline)

                            Spacer()

                            Picker(
                                "Tecla do botão \(slot.face)",
                                selection: Binding(
                                    get: { engine.scancode(for: slot) },
                                    set: { engine.setScancode($0, for: slot) }
                                )
                            ) {
                                ForEach(nordelunaKeyboardKeys) { key in
                                    Text(key.label).tag(key.scancode)
                                }
                            }
                            .pickerStyle(.menu)
                            .tint(.cyan)
                        }
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 14))
                    }
                }
            }
            .frame(maxHeight: 270)

            Button("Concluído", action: onDone)
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
        }
        .foregroundStyle(.white)
        .padding(22)
        .frame(maxWidth: 560)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 24))
        .padding(.horizontal, 24)
    }
}
