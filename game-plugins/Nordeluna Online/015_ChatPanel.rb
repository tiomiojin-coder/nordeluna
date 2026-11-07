module NordelunaOnline
  module ChatPanel
    class << self
      def modal?; !!@modal; end

      def format_message(row)
        "[#{Time.at(row['timestamp']).strftime('%H:%M')}] #{row['nick']}: #{row['text']}"
      end

      def wrap(bitmap, text, width)
        @wrap_cache ||= {}
        key = [text.to_s, width, bitmap.font.size]
        return @wrap_cache[key] if @wrap_cache.key?(key)
        lines = []
        text.to_s.split("\n", -1).each do |paragraph|
          current = ""
          paragraph.each_char do |character|
            if !current.empty? && bitmap.text_size(current + character).width > width
              lines << current
              current = ""
            end
            current += character
          end
          lines << current
        end
        @wrap_cache.shift while @wrap_cache.length >= 160
        @wrap_cache[key] = lines
      end

      def dispose_sprite(sprite)
        return unless sprite && !sprite.disposed?
        sprite.bitmap.dispose if sprite.bitmap && !sprite.bitmap.disposed?
        sprite.dispose unless sprite.disposed?
      end

      def create_sprite(width, height)
        sprite = Sprite.new
        sprite.bitmap = Bitmap.new(width, height)
        sprite.z = 95000
        sprite
      end

      def text(bitmap, value, x, y, width, size = 16, color = nil)
        bitmap.font.size = size
        bitmap.font.color = color || Color.new(237, 244, 255)
        bitmap.draw_text(x, y, width, 22, value.to_s)
      end

      def mouse_click
        return nil unless Input.const_defined?(:MOUSELEFT) && Input.respond_to?(:mouse_x) && Input.respond_to?(:mouse_y)
        return nil unless Input.trigger?(Input::MOUSELEFT)
        [Input.mouse_x, Input.mouse_y]
      end

      def inside?(point, rectangle)
        point && point[0] >= rectangle[0] && point[0] < rectangle[0] + rectangle[2] &&
          point[1] >= rectangle[1] && point[1] < rectangle[1] + rectangle[3]
      end

      def button(bitmap, label, rectangle)
        x, y, width, height = rectangle
        bitmap.fill_rect(x, y, width, height, Color.new(32, 68, 94))
        text(bitmap, label, x + 6, y + 3, width - 12, width < 100 ? 14 : 16)
      end

      def update
        return if @disabled
        return if modal?
        unless MapChannel.managed? && MapChannel.safe_map?
          @collapsed.visible = false if @collapsed
          return
        end
        width = [360, Graphics.width - 16].min
        if !@collapsed || @collapsed.disposed? || @collapsed_width != width
          dispose_sprite(@collapsed)
          @collapsed = create_sprite(width, 78)
          @collapsed_width = width
          @collapsed_signature = nil
        end
        @collapsed.x = (Graphics.width - width) / 2
        @collapsed.y = 8
        @collapsed.visible = true
        signature = [MapChannel.revision, MapChannel.connection_label, MapChannel.members]
        if @collapsed_signature != signature
          bitmap = @collapsed.bitmap
          bitmap.clear
          bitmap.fill_rect(0, 0, width, 78, Color.new(12, 27, 45, 220))
          text(bitmap, "CHAT | #{MapChannel.room_name} (#{MapChannel.members})  [+]", 8, 2, width - 16, 16, Color.new(101, 222, 245))
          text(bitmap, MapChannel.connection_label, 8, 23, width - 16, 14)
          latest = MapChannel.messages.last
          text(bitmap, latest ? format_message(latest) : "Toque para abrir o historico e escrever.", 8, 47, width - 16, 14)
          @collapsed_signature = signature
        end
        open_chat if inside?(mouse_click, [@collapsed.x, @collapsed.y, width, 78])
      rescue StandardError => error
        NordelunaOnline.record_online_error(error, "chat_panel")
        dispose
        @disabled = true
      end

      def compose
        value = pbMessageFreeText(_INTL("Mensagem para sala {1} (ate 120 caracteres):", MapChannel.room_name), "", false, 120)
        MapChannel.queue_message(value) unless value.to_s.strip.empty?
      rescue Error => error
        pbMessage(_INTL("Chat: {1}", error.message))
      end

      def open_chat
        unless MapChannel.managed?
          pbMessage(_INTL("Entre em uma sala em Online > Sala e chat."))
          return
        end
        modal_loop(:chat)
      end

      def diagnostic_lines
        data = NordelunaOnline.diagnostic_snapshot
        remote = data["remote"]
        error = data["last_error"]
        ["Cliente online: #{data['client']}", "Build: #{data['build']}",
          "Servidor: #{data['server']}",
          "Versao do servidor: #{remote['version'] || 'nao informada'}",
          "Protocolo: #{remote['protocol'] || '--'} | revisao: #{remote['revision'] || '--'}",
          "Ultima latencia: #{remote['latency_ms'] ? remote['latency_ms'].to_s + ' ms' : '--'}",
          "Sala: #{data['room']} | #{data['state']}",
          error ? "Ultimo erro (#{Time.at(error['time']).strftime('%H:%M')} / #{error['action']}): #{error['message']}" : "Ultimo erro: nenhum nesta sessao."]
      end

      def modal_loop(kind)
        entered = false
        return if modal?
        @modal = true
        entered = true
        @disabled = false
        @wrap_cache = {}
        previous_menu = $game_temp.in_menu
        previous_scene = $scene
        $game_temp.in_menu = true
        @collapsed.visible = false if @collapsed
        width, height = Graphics.width - 16, Graphics.height - 16
        screen = create_sprite(width, height)
        screen.x = screen.y = 8
        scroll = 0
        loop do
          Graphics.update
          Input.update
          break unless $scene == previous_scene
          MapChannel.update
          bitmap = screen.bitmap
          bitmap.clear
          bitmap.fill_rect(0, 0, width, height, Color.new(10, 22, 38, 250))
          title = kind == :chat ? "Chat | Sala #{MapChannel.room_name} (#{MapChannel.members})" : "Diagnostico Online"
          text(bitmap, title, 10, 6, width - 20, 20, Color.new(101, 222, 245))
          text(bitmap, kind == :chat ? MapChannel.connection_label : "Versoes, conexao e ultimo erro", 10, 29, width - 80, 14)
          bitmap.font.size = 16
          rows = if kind == :chat
                   MapChannel.messages.flat_map { |row| wrap(bitmap, format_message(row), width - 24) }
                 else
                   diagnostic_lines.flat_map { |line| wrap(bitmap, line, width - 24) }
                 end
          rows = ["Nenhuma mensagem nesta sala."] if rows.empty?
          visible_rows = [(height - 128) / 20, 1].max
          maximum = [rows.length - visible_rows, 0].max
          scroll = [[scroll, 0].max, maximum].min
          start = kind == :chat ? maximum - scroll : scroll
          rows.slice(start, visible_rows).to_a.each_with_index { |line, i| text(bitmap, line, 10, 57 + i * 20, width - 20) }
          up, down = [width - 64, 29, 26, 24], [width - 34, 29, 26, 24]
          button_width = (width - 40) / 3
          first, second, last = [10, height - 40, button_width, 30], [20 + button_width, height - 40, button_width, 30], [30 + button_width * 2, height - 40, button_width, 30]
          button(bitmap, "^", up)
          button(bitmap, "v", down)
          button(bitmap, kind == :chat ? "Escrever" : "Testar", first)
          button(bitmap, kind == :chat ? "Reconectar" : "Copiar", second)
          button(bitmap, kind == :chat ? "Recolher" : "Voltar", last)
          notice = MapChannel.notice
          text(bitmap, notice, 10, height - 67, width - 20, 13, Color.new(247, 206, 123)) if kind == :chat && notice
          point = mouse_click
          point = [point[0] - 8, point[1] - 8] if point
          break if Input.trigger?(Input::BACK) || inside?(point, last)
          if Input.trigger?(Input::UP) || inside?(point, up)
            scroll += kind == :chat ? 1 : -1
          elsif Input.trigger?(Input::DOWN) || inside?(point, down)
            scroll += kind == :chat ? -1 : 1
          elsif Input.trigger?(Input::USE) || inside?(point, first)
            if kind == :chat
              compose
            else
              begin
                NordelunaOnline.test_connection(false)
              rescue Error => error
                NordelunaOnline.record_online_error(error, "health")
              end
            end
          elsif inside?(point, second)
            begin
              if kind == :chat
                MapChannel.connect(MapChannel.room_name)
              elsif Input.respond_to?(:clipboard=)
                Input.clipboard = diagnostic_lines.join("\n")
                pbMessage(_INTL("Diagnostico copiado, sem tokens de sessao."))
              end
            rescue Error => error
              pbMessage(error.message)
            end
          end
        end
      rescue StandardError => error
        NordelunaOnline.record_online_error(error, "chat_panel")
        pbMessage(_INTL("Nao foi possivel abrir este painel. O erro foi registrado no diagnostico."))
      ensure
        if entered
          dispose_sprite(screen)
          $game_temp.in_menu = previous_menu if $game_temp
          @modal = false
          @collapsed_signature = nil
          Input.update
        end
      end

      def hide
        @collapsed.visible = false if @collapsed && !@collapsed.disposed?
      end

      def dispose
        dispose_sprite(@collapsed)
        @collapsed = nil
        @wrap_cache = {}
      end
    end
  end

  def self.room_menu
    loop do
      label = "Sala #{MapChannel.room_name}: #{MapChannel.connection_label}"
      choice = pbMessage(label, [_INTL("Entrar na praca publica"), _INTL("Entrar por codigo"),
        _INTL("Criar sala"), _INTL("Abrir chat"), _INTL("Copiar codigo"), _INTL("Sair da sala"), _INTL("Voltar")], 7)
      case choice
      when 0 then return :sent if MapChannel.connect("PRACA")
      when 1
        code = pbMessageFreeText(_INTL("Codigo da sala (8 caracteres):"), "", false, 8).strip.upcase
        return :sent if !code.empty? && MapChannel.connect(code)
      when 2
        code = Random.bytes(8).bytes.map { |byte| "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"[byte % 32] }.join
        if MapChannel.connect(code)
          pbMessage(_INTL("Sala {1}. Envie o codigo a quem vai participar.", code))
          return :sent
        end
      when 3 then ChatPanel.open_chat
      when 4
        Input.clipboard = MapChannel.room_name if Input.respond_to?(:clipboard=)
        pbMessage(_INTL("Sala: {1}", MapChannel.room_name))
      when 5
        online_area = defined?(Areas) && Areas.active?
        MapChannel.disconnect
        return :sent if online_area
      else return
      end
    end
  rescue Error => error
    pbMessage(_INTL("Sala: {1}", error.message))
  end
end

EventHandlers.add(:on_frame_update, :nordeluna_chat_panel, proc { NordelunaOnline::ChatPanel.update })
EventHandlers.add(:on_start_battle, :nordeluna_chat_hide, proc { NordelunaOnline::ChatPanel.hide })

if defined?(Scene_Map)
  module NordelunaChatMapCleanup
    def dispose
      NordelunaOnline::ChatPanel.dispose
      NordelunaOnline::MapChannel.abandon if $scene != self
      super
    end
  end
  Scene_Map.prepend(NordelunaChatMapCleanup)
end
MenuHandlers.add(:pause_menu, :nordeluna_room_chat, {
  "name" => _INTL("Sala e chat"), "order" => 47, "condition" => proc { !$game_temp.in_battle },
  "effect" => proc { |menu| next NordelunaOnline.run_pause_action(menu) { NordelunaOnline.room_menu } }
})
MenuHandlers.add(:pause_menu, :nordeluna_diagnostics, {
  "name" => _INTL("Diagnostico online"), "order" => 48, "condition" => proc { !$game_temp.in_battle },
  "effect" => proc { |menu| next NordelunaOnline.run_pause_action(menu) { NordelunaOnline::ChatPanel.modal_loop(:diagnostic) } }
})
