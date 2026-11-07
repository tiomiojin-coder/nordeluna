module NordelunaOnline
  class RemotePlayerVisual
    attr_reader :data, :label, :revision
    def initialize(data)
      @sprite = Sprite.new
      @label = Sprite.new
      @label.bitmap = Bitmap.new(200, 32)
      pbSetSystemFont(@label.bitmap)
      @label.bitmap.font.size = NICK_FONT_SIZE
      @label.ox = 100
      @label.z = 9000
      @x, @y = data["x"].to_f, data["y"].to_f
      @revision = nil
      apply(data)
    rescue StandardError
      dispose
      raise
    end

    def apply(row)
      return if @data && row["seq"] <= @data["seq"]
      now = NordelunaOnline.now
      @from_x, @from_y = @x, @y
      if (@x - row["x"]).abs + (@y - row["y"]).abs > 4
        @from_x, @from_y = row["x"].to_f, row["y"].to_f
      end
      @moved_at = @seen_at = now
      @data = (@data || {}).merge(row)
      return if @revision == row["profile_revision"]
      @revision = row["profile_revision"]
      @animated&.dispose
      @animated = nil
      @label.bitmap.clear
      name = NordelunaOnline.safe_label(@data["name"])
      @label.bitmap.font.color = Color.new(*NICK_OUTLINE)
      @label.bitmap.draw_text(1, 1, 198, 30, name, 1)
      @label.bitmap.font.color = Color.new(*NICK_COLOR)
      @label.bitmap.draw_text(0, 0, 198, 30, name, 1)
      character = @data["character"]
      valid = character.is_a?(String) && character.length.between?(1, 128) && !character.match?(/[\\<>\x00-\x1f]/) &&
        !character.start_with?("/") && !character.split("/").include?("..")
      path = "Graphics/Characters/#{character}"
      path = "Graphics/Characters/#{$game_player.character_name}" unless valid && pbResolveBitmap(path)
      @animated = AnimatedBitmap.new(path)
    end

    def update(visible)
      now = NordelunaOnline.now
      factor = [[(now - @moved_at) / POSITION_INTERVAL, 0.0].max, 1.0].min
      @x = @from_x + (@data["x"] - @from_x) * factor
      @y = @from_y + (@data["y"] - @from_y) * factor
      close = (@x - $game_player.x).abs + (@y - $game_player.y).abs <= REMOTE_DISTANCE
      show = visible && close && now - @seen_at < 6
      @sprite.visible = show
      @label.visible = show && SHOW_NICKNAMES
      return unless show && @animated
      @animated.update
      @sprite.bitmap = @animated.bitmap
      width, height = @animated.width / 4, @animated.height / 4
      return if width < 1 || height < 1
      frame = @data["moving"] ? (@data["frame"] + ((now - @moved_at) / 0.15).floor) % 4 : @data["frame"]
      @sprite.src_rect.set(frame * width, (@data["direction"] / 2 - 1) * height, width, height)
      @sprite.ox, @sprite.oy = width / 2, height
      @sprite.x = ((@x + 0.5) * 32 - $game_map.display_x / 4.0).round
      @sprite.y = ((@y + 1) * 32 - $game_map.display_y / 4.0).round
      @sprite.z = @sprite.y
      @label.x = @sprite.x
      @label.y = @sprite.y - height - NICK_OFFSET - 24
      @label.opacity = 255
    end

    def dispose
      return if @disposed
      @disposed = true
      @animated.dispose if @animated && !@animated.bitmap.disposed?
      @animated = nil
      if @label && !@label.disposed?
        @label.bitmap.dispose if @label.bitmap && !@label.bitmap.disposed?
        @label.dispose unless @label.disposed?
      end
      @sprite.dispose if @sprite && !@sprite.disposed?
    end
  end

  module Ghosts
    class << self
      def rows; @players ||= {}; end
      def known_metadata; rows.transform_values(&:revision); end

      def synchronize(peers)
        raise Error, "Lista de jogadores invalida." unless peers.is_a?(Array) && peers.length <= 40
        clear if @map_id != $game_map.map_id
        @map_id = $game_map.map_id
        present = []
        peers.each do |row|
          valid = row.is_a?(Hash) && row["id"].is_a?(String) && row["id"].match?(/\A[0-9a-f]{16}\z/) &&
            %w[x y seq frame direction map].all? { |key| row[key].is_a?(Integer) } &&
            row["x"].between?(0, 9999) && row["y"].between?(0, 9999) && row["seq"] >= 0 && row["frame"].between?(0, 3) &&
            [2,4,6,8].include?(row["direction"]) && row["map"] == @map_id && [true,false].include?(row["moving"]) &&
            row["profile_revision"].is_a?(String) && row["profile_revision"].match?(/\A[0-9a-f]{16}\z/)
          raise Error, "Representacao remota invalida." unless valid
          id = row["id"]
          metadata = rows[id] && rows[id].data
          if !metadata || metadata["profile_revision"] != row["profile_revision"]
            raise Error, "Identidade remota invalida." unless NordelunaOnline.valid_nickname?(row["name"]) &&
              row["account_id"].is_a?(String) && row["account_id"].match?(/\A[0-9a-f]{32}\z/) && row["character"].is_a?(String)
          end
          present << id
          rows[id] ? rows[id].apply(row) : rows[id] = RemotePlayerVisual.new(row)
        end
        (rows.keys - present).each { |id| rows.delete(id).dispose }
      end

      def update
        unless Areas.active? && Areas.online_map?($game_map&.map_id)
          clear
          return
        end
        clear if @map_id && @map_id != $game_map.map_id
        occupied = []
        rows.sort.each do |_id, visual|
          visual.update(MapChannel.safe_map?)
          label = visual.label
          next unless label.visible
          # At most two small shifts; crowded names fade rather than forming a tower.
          overlaps = occupied.count { |x,y| (label.x - x).abs < 110 && (label.y - y).abs < 18 }
          label.y -= [overlaps, 2].min * 12
          label.opacity = 170 if overlaps > 2
          occupied << [label.x, label.y]
        end
        update_local_label
      end

      def update_local_label
        unless @local_label
          @local_label = Sprite.new
          @local_label.bitmap = Bitmap.new(200, 32)
          pbSetSystemFont(@local_label.bitmap)
          @local_label.bitmap.font.size = NICK_FONT_SIZE
          @local_label.ox = 100
          @local_label.z = 9000
        end
        name = NordelunaOnline.nickname
        if @local_name != name
          @local_name = name
          @local_label.bitmap.clear
          @local_label.bitmap.font.color = Color.new(*NICK_OUTLINE)
          @local_label.bitmap.draw_text(1,1,198,30,name,1)
          @local_label.bitmap.font.color = Color.new(*NICK_COLOR)
          @local_label.bitmap.draw_text(0,0,198,30,name,1)
        end
        @local_label.x = $game_player.screen_x
        @local_label.y = $game_player.screen_y - ($game_player.sprite_size&.last || 32) - NICK_OFFSET - 24
        @local_label.visible = SHOW_NICKNAMES && MapChannel.safe_map?
      end

      def clear
        return if (!@players || @players.empty?) && !@local_label && !@map_id
        rows.each_value(&:dispose)
        @players = {}
        @map_id = nil
        if @local_label && !@local_label.disposed?
          @local_label.bitmap.dispose if @local_label.bitmap && !@local_label.bitmap.disposed?
          @local_label.dispose unless @local_label.disposed?
        end
        @local_label = @local_name = nil
      end

      def interact
        nearby = rows.values.select { |visual| (visual.data["x"] - $game_player.x).abs + (visual.data["y"] - $game_player.y).abs <= 2 }
        if nearby.empty?
          pbMessage(_INTL("Nao ha jogadores proximos nesta area e instancia."))
          return
        end
        choice = pbMessage(_INTL("Escolha um treinador:"), nearby.map { |v| v.data["name"] } + [_INTL("Cancelar")], nearby.length + 1)
        return unless choice >= 0 && choice < nearby.length
        peer = nearby[choice].data
        command = pbMessage(_INTL("Treinador: {1}", peer["name"]),
          [_INTL("Ver perfil"), _INTL("Desafiar: criar sala"), _INTL("Trocar: criar sala"), _INTL("Cancelar")], 4)
        case command
        when 0
          pbMessage(_INTL("Treinador: {1}\nID online: {2}\nInstancia: {3}", peer["name"], peer["account_id"], MapChannel.room_name))
        when 1,2
          pbMessage(_INTL("Crie a sala e envie o codigo para {1}. As regras e confirmacoes existentes continuam valendo.", peer["name"]))
          NordelunaOnline.connect(command == 1 ? "battle" : "trade", false)
        end
      end
    end
  end
end

EventHandlers.add(:on_frame_update, :nordeluna_remote_players, proc { NordelunaOnline::Ghosts.update })
MenuHandlers.add(:pause_menu, :nordeluna_nearby_players, {
  "name" => _INTL("Jogadores proximos"), "order" => 49,
  "condition" => proc { NordelunaOnline::Areas.active? && !$game_temp.in_battle },
  "effect" => proc { |menu| next NordelunaOnline.run_pause_action(menu) { NordelunaOnline::Ghosts.interact } }
})
