import SwiftUI

private struct TouchKeyButton: View {
    let title: String
    let scancode: Int32
    var size: CGFloat = 64
    @State private var pressed = false

    var body: some View {
        Text(title)
            .font(.system(size: size * 0.32, weight: .bold, design: .rounded))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(.ultraThinMaterial, in: Circle())
            .overlay(Circle().stroke(.white.opacity(pressed ? 0.9 : 0.35), lineWidth: 2))
            .scaleEffect(pressed ? 0.9 : 1)
            .contentShape(Circle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in
                        guard !pressed else { return }
                        pressed = true
                        NordelunaEngine.shared.setKey(scancode, pressed: true)
                    }
                    .onEnded { _ in release() }
            )
            .onDisappear { release() }
    }

    private func release() {
        guard pressed else { return }
        pressed = false
        NordelunaEngine.shared.setKey(scancode, pressed: false)
    }
}

private struct DirectionPad: View {
    @State private var held = Set<Int32>()

    var body: some View {
        GeometryReader { proxy in
            ZStack {
                Circle().fill(.ultraThinMaterial)
                Circle().stroke(.white.opacity(0.35), lineWidth: 2)
                Image(systemName: "arrowtriangle.up.fill")
                    .offset(y: -44)
                Image(systemName: "arrowtriangle.down.fill")
                    .offset(y: 44)
                Image(systemName: "arrowtriangle.left.fill")
                    .offset(x: -44)
                Image(systemName: "arrowtriangle.right.fill")
                    .offset(x: 44)
                Circle().fill(.white.opacity(0.18)).frame(width: 42, height: 42)
            }
            .foregroundStyle(.white.opacity(0.8))
            .contentShape(Circle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        update(location: value.location, size: proxy.size)
                    }
                    .onEnded { _ in updateHeld([]) }
            )
        }
        .frame(width: 154, height: 154)
        .onDisappear { updateHeld([]) }
    }

    private func update(location: CGPoint, size: CGSize) {
        let dx = location.x - size.width / 2
        let dy = location.y - size.height / 2
        guard (dx * dx) + (dy * dy) > 324 else {
            updateHeld([])
            return
        }
        var next = Set<Int32>()
        if abs(dx) > 14 { next.insert(dx < 0 ? Int32(GAMECORE_SCANCODE_LEFT) : Int32(GAMECORE_SCANCODE_RIGHT)) }
        if abs(dy) > 14 { next.insert(dy < 0 ? Int32(GAMECORE_SCANCODE_UP) : Int32(GAMECORE_SCANCODE_DOWN)) }
        updateHeld(next)
    }

    private func updateHeld(_ next: Set<Int32>) {
        for key in held.subtracting(next) { NordelunaEngine.shared.setKey(key, pressed: false) }
        for key in next.subtracting(held) { NordelunaEngine.shared.setKey(key, pressed: true) }
        held = next
    }
}

struct TouchControlsView: View {
    var body: some View {
        VStack {
            HStack {
                Button {
                    NordelunaEngine.shared.controlsVisible.toggle()
                } label: {
                    Image(systemName: "eye.slash.fill")
                        .frame(width: 44, height: 44)
                        .background(.ultraThinMaterial, in: Circle())
                }
                Spacer()
                Button {
                    NordelunaEngine.shared.pause()
                } label: {
                    Image(systemName: "pause.fill")
                        .frame(width: 44, height: 44)
                        .background(.ultraThinMaterial, in: Circle())
                }
            }
            .foregroundStyle(.white)

            Spacer()

            HStack(alignment: .bottom) {
                DirectionPad()
                Spacer(minLength: 24)
                ZStack {
                    TouchKeyButton(title: "A", scancode: Int32(GAMECORE_SCANCODE_Z), size: 72)
                        .offset(x: 42, y: -18)
                    TouchKeyButton(title: "B", scancode: Int32(GAMECORE_SCANCODE_X), size: 66)
                        .offset(x: -28, y: 24)
                    TouchKeyButton(title: "X", scancode: Int32(GAMECORE_SCANCODE_A), size: 48)
                        .offset(x: -32, y: -52)
                    TouchKeyButton(title: "Y", scancode: Int32(GAMECORE_SCANCODE_S), size: 48)
                        .offset(x: 30, y: 54)
                }
                .frame(width: 160, height: 154)
            }
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 14)
    }
}
