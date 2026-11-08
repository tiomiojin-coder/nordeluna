module NordelunaOnline
  module PlayerCardVisual
    def apply(row)
      if row.key?('status') && !OnlineUI::STATES.key?(row['status'])
        raise Error,'Estado remoto invalido.'
      end
      super
      refresh_card_label
    end

    def refresh_card_label
      show_badges=defined?(CosmeticBadges) && CosmeticBadges.show?
      signature=[@revision,@data['status'] || 'available',@data['badge'] || '',show_badges]
      if @card_label_signature!=signature
        if @label.bitmap.height<60
          @label.bitmap.dispose
          @label.bitmap=Bitmap.new(264,60)
          @label.ox=132
          pbSetSystemFont(@label.bitmap)
        end
        @card_width=OnlineUI.nameplate(@label.bitmap,@data['name'],signature[1],signature[2])
        @card_label_signature=signature
        @badges_visible=show_badges
      end
    end

    def update(visible)
      refresh_card_label if defined?(CosmeticBadges) && @badges_visible!=CosmeticBadges.show?
      result=super
      if @label.visible
        @label.y=[@label.y-20,2].max
        half=(@card_width || 110)/2+2
        @label.x=[[@label.x,half].max,Graphics.width-half].min
      end
      result
    end

    def hit_rectangle
      return unless @sprite && !@sprite.disposed? && @sprite.visible && @sprite.bitmap
      width=[@sprite.src_rect.width,40].max
      height=[@sprite.src_rect.height,48].max
      [@sprite.x-width/2,@sprite.y-height,width,height]
    end
  end
  RemotePlayerVisual.prepend(PlayerCardVisual)

  module PlayerCardInteraction
    def update_local_label
      super
      return unless @local_label
      if @local_label.bitmap.height<60
        @local_label.bitmap.dispose
        @local_label.bitmap=Bitmap.new(264,60)
        @local_label.ox=132
        pbSetSystemFont(@local_label.bitmap)
      end
      payload=Friends.payload
      state=payload['busy'] ? payload['activity'] : Friends.status
      badge=defined?(CosmeticBadges) ? CosmeticBadges.own : ''
      signature=[NordelunaOnline.nickname,state,badge,defined?(CosmeticBadges) && CosmeticBadges.show?]
      if @local_card_signature!=signature
        @local_card_width=OnlineUI.nameplate(@local_label.bitmap,signature[0],state,badge)
        @local_card_signature=signature
      end
      @local_label.y=[@local_label.y-20,2].max
      half=(@local_card_width || 110)/2+2
      @local_label.x=[[@local_label.x,half].max,Graphics.width-half].min
    end

    def clear
      @local_card_signature=@card_touch=nil
      super
    end

    def interact; SocialHub.nearby; end

    def touch_allowed?
      Areas.active? && MapChannel.safe_map? && !OnlineUI.modal? && !ChatPanel.modal? &&
        !$game_temp.in_menu && !$game_temp.message_window_showing && !pbMapInterpreterRunning? &&
        (! $game_player.respond_to?(:moving?) || !$game_player.moving?)
    end

    def touch_player
      unless touch_allowed?
        @card_touch=nil
        return
      end
      point=OnlineUI.pointer
      if OnlineUI.pointer_start? && point
        # The bottom corners are normally occupied by the port's virtual pad.
        corner=point[1]>Graphics.height*0.60 && (point[0]<Graphics.width*0.27 || point[0]>Graphics.width*0.73)
        @card_touch=corner || ChatPanel.hit_test(point) ? nil : {point:point,at:NordelunaOnline.now,moved:false}
      end
      return unless @card_touch
      if !point || (point[0]-@card_touch[:point][0]).abs>8 || (point[1]-@card_touch[:point][1]).abs>8
        @card_touch[:moved]=true
      end
      return if OnlineUI.pointer_down?
      touch=@card_touch
      @card_touch=nil
      return if touch[:moved] || NordelunaOnline.now-touch[:at]>0.6
      candidates=rows.values.select { |visual| (rectangle=visual.hit_rectangle) && ChatPanel.inside?(point,rectangle) }
      return if candidates.empty?
      if candidates.length==1
        SocialHub.peer_card(candidates.first.data)
      else
        choice=OnlineUI.choose('Treinadores neste ponto',candidates.map { |visual| visual.data['name'] }+['Voltar'],candidates.length)
        SocialHub.peer_card(candidates[choice].data) if choice>=0 && choice<candidates.length
      end
    rescue StandardError => error
      @card_touch=nil
      NordelunaOnline.record_online_error(error,'player_card_touch')
    end
  end
  Ghosts.singleton_class.prepend(PlayerCardInteraction)
end
EventHandlers.add(:on_frame_update,:nordeluna_player_touch,proc { NordelunaOnline::Ghosts.touch_player })
