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
        bitmap.draw_text(x, y, width, [size + 10, 26].max, value.to_s)
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

      def hit_test(point)
        @collapsed && !@collapsed.disposed? && @collapsed.visible &&
          inside?(point,[@collapsed.x,@collapsed.y,@collapsed_width,30])
      end

      def button(bitmap, label, rectangle)
        x, y, width, height = rectangle
        box(bitmap, x, y, width, height, Color.new(31, 58, 78))
        bitmap.font.size = width < 90 ? 14 : 16
        bitmap.font.color = Color.new(229, 241, 248)
        bitmap.draw_text(x + 3, y, width - 6, height, label, 1)
      end

      # Small pixel-rounded surfaces fit the game's native 512x384 canvas.
      def box(bitmap, x, y, width, height, color)
        bitmap.fill_rect(x + 3, y, width - 6, height, color)
        bitmap.fill_rect(x, y + 3, 3, height - 6, color)
        bitmap.fill_rect(x + width - 3, y + 3, 3, height - 6, color)
      end

      def fit(bitmap, value, width)
        value = value.to_s
        return value if bitmap.text_size(value).width <= width
        result = value.dup
        result.chop! while !result.empty? && bitmap.text_size(result + "...").width > width
        result + "..."
      end

      def chat_rows(bitmap, width)
        MapChannel.messages.flat_map do |row|
          own = row['nick'] == NordelunaOnline.nickname
          [["#{row['nick']}  #{Time.at(row['timestamp']).strftime('%H:%M')}", :author, own]] +
            wrap(bitmap, row['text'], width).map { |line| [line, :body, own] } + [["", :space, own]]
        end
      end

      def modal_bounds
        width = [408, Graphics.width - 24].min
        height = [316, Graphics.height - 24].min
        [(Graphics.width - width) / 2, (Graphics.height - height) / 2, width, height]
      end

      def update
        return if @disabled
        return if modal?
        unless MapChannel.managed? && MapChannel.safe_map?
          @collapsed.visible = false if @collapsed
          return
        end
        room = MapChannel.room_name
        if @seen_room != room
          @seen_room = room
          @seen_message = MapChannel.messages.last && MapChannel.messages.last['id']
        end
        latest_id = MapChannel.messages.last && MapChannel.messages.last['id']
        @seen_message = nil if latest_id && @seen_message && latest_id < @seen_message
        unseen = MapChannel.messages.count { |row| @seen_message ? row['id'] > @seen_message : true }
        # No message preview over the map: the history remains one tap away.
        width, height = [168, Graphics.width - 32].min, 30
        if !@collapsed || @collapsed.disposed? || @collapsed_width != width
          dispose_sprite(@collapsed)
          @collapsed = create_sprite(width, height)
          @collapsed_width = width
          @collapsed_signature = nil
        end
        @collapsed.x = (Graphics.width - width) / 2
        @collapsed.y = 8
        @collapsed.visible = true
        signature = [room, MapChannel.connection_label, MapChannel.members, unseen]
        if @collapsed_signature != signature
          bitmap = @collapsed.bitmap
          bitmap.clear
          box(bitmap, 0, 0, width, height, Color.new(9, 21, 36, 232))
          # Speech icon and a quiet connection indicator replace two text lines.
          box(bitmap, 9, 8, 15, 11, Color.new(99, 216, 229))
          bitmap.fill_rect(12, 18, 4, 4, Color.new(99, 216, 229))
          bitmap.fill_rect(12, 11, 9, 2, Color.new(9, 21, 36))
          status_color = MapChannel.active? ? Color.new(100, 218, 171) : Color.new(244, 190, 102)
          bitmap.fill_rect(width - 12, 12, 5, 5, status_color)
          label_width = width - (unseen > 0 ? 79 : 47)
          bitmap.font.size = 14
          label = fit(bitmap, room == 'PRACA' ? "Praça (#{MapChannel.members})" : room, label_width)
          text(bitmap, label, 31, 3, label_width, 14)
          if unseen > 0
            badge = unseen > 99 ? "99+" : unseen.to_s
            box(bitmap, width - 45, 6, 26, 18, Color.new(39, 104, 125))
            bitmap.font.size = 12
            bitmap.draw_text(width - 45, 5, 26, 20, badge, 1)
          end
          @collapsed_signature = signature
        end
        open_chat if inside?(mouse_click, [@collapsed.x, @collapsed.y, width, height])
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
        left, top, width, height = modal_bounds
        screen = create_sprite(width, height)
        screen.x, screen.y = left, top
        scroll = 0
        focus = 0
        loop do
          Graphics.update
          Input.update
          break unless $scene == previous_scene
          MapChannel.update
          bitmap = screen.bitmap
          bitmap.clear
          if defined?(OnlineUI) && OnlineUI.respond_to?(:draw_background)
            OnlineUI.draw_background(bitmap,width,height)
          else
            box(bitmap, 0, 0, width, height, Color.new(9, 20, 33, 248))
          end
          bitmap.fill_rect(8, 0, width - 16, 2, Color.new(78, 192, 211))
          title = kind == :chat ? "Chat da sala" : "Diagnostico Online"
          text(bitmap, title, 14, 7, width - 28, 19, Color.new(156, 235, 242))
          subtitle = kind == :chat ? "#{MapChannel.room_name} / #{MapChannel.members} online / #{MapChannel.connection_label}" : "Versoes, conexao e ultimo erro"
          bitmap.font.size = 13
          text(bitmap, fit(bitmap, subtitle, width - 100), 14, 29, width - 100, 13, Color.new(156, 177, 195))
          bitmap.fill_rect(14, 54, width - 28, 1, Color.new(40, 62, 80))
          bitmap.font.size = 16
          rows = if kind == :chat
                   chat_rows(bitmap, width - 48)
                 else
                   diagnostic_lines.flat_map { |line| wrap(bitmap, line, width - 40).map { |part| [part, :body, false] } }
                 end
          rows = [["Nenhuma mensagem ainda. Diga oi!", :body, false]] if rows.empty?
          visible_rows = [(height - 130) / 22, 1].max
          maximum = [rows.length - visible_rows, 0].max
          scroll = [[scroll, 0].max, maximum].min
          start = kind == :chat ? maximum - scroll : scroll
          start += 1 while start < rows.length - 1 && rows[start][1] == :space
          rows.slice(start, visible_rows).to_a.each_with_index do |(line, style, own), i|
            next if style == :space
            y = 64 + i * 22
            if kind == :chat
              bitmap.fill_rect(14, y, width - 28, 22, own ? Color.new(21, 48, 61) : Color.new(18, 34, 50))
              bitmap.fill_rect(14, y, 2, 22, own ? Color.new(111, 188, 157) : Color.new(65, 113, 143))
            end
            color = style == :author ? (own ? Color.new(137, 221, 179) : Color.new(117, 207, 232)) : Color.new(232, 240, 248)
            text(bitmap, line, 23, y - 2, width - 46, style == :author ? 13 : 16, color)
          end
          up, down = [width - 64, 29, 26, 24], [width - 34, 29, 26, 24]
          button_width = (width - 40) / 3
          first, second, last = [10, height - 40, button_width, 30], [20 + button_width, height - 40, button_width, 30], [30 + button_width * 2, height - 40, button_width, 30]
          button(bitmap, "^", up)
          button(bitmap, "v", down)
          button(bitmap, kind == :chat ? "Escrever" : "Testar", first)
          button(bitmap, kind == :chat ? "Reconectar" : "Copiar", second)
          button(bitmap, kind == :chat ? "Recolher" : "Voltar", last)
          selected=[first,second,last][focus]
          bitmap.fill_rect(selected[0]+4,selected[1]+selected[3]-3,selected[2]-8,2,Color.new(245,209,117))
          notice = MapChannel.notice
          hint = notice || "Esq/dir: botoes | Confirmar: usar | Cima/baixo: historico"
          bitmap.font.size = 12
          text(bitmap, fit(bitmap, hint, width - 28), 14, height - 68, width - 28, 12, Color.new(173, 188, 201))
          point = mouse_click
          point = [point[0] - left, point[1] - top] if point
          break if Input.trigger?(Input::BACK) || inside?(point, last) || (Input.trigger?(Input::USE) && focus==2)
          if Input.trigger?(Input::UP) || inside?(point, up)
            scroll += kind == :chat ? 1 : -1
          elsif Input.trigger?(Input::DOWN) || inside?(point, down)
            scroll += kind == :chat ? -1 : 1
          elsif Input.trigger?(Input::LEFT)
            focus=(focus-1)%3
          elsif Input.trigger?(Input::RIGHT)
            focus=(focus+1)%3
          elsif (Input.trigger?(Input::USE) && focus==0) || inside?(point, first)
            if kind == :chat
              compose
            else
              begin
                NordelunaOnline.test_connection(false)
              rescue Error => error
                NordelunaOnline.record_online_error(error, "health")
              end
            end
          elsif (Input.trigger?(Input::USE) && focus==1) || inside?(point, second)
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
          if kind == :chat
            @seen_room = MapChannel.room_name
            @seen_message = MapChannel.messages.last && MapChannel.messages.last['id']
          end
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
      options = [_INTL("Entrar na praca publica"), _INTL("Entrar por codigo"),
        _INTL("Criar sala"), _INTL("Abrir chat"), _INTL("Copiar codigo"), _INTL("Sair da sala"), _INTL("Voltar")]
      choice = defined?(OnlineUI) ? OnlineUI.choose("Salas", options, 6, label) : pbMessage(label, options, 7)
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
