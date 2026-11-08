module NordelunaOnline
  class ModerationError < Error
    attr_reader :moderation_code,:expires_at
    def initialize(code,message,expires_at=0)
      super(message.to_s.gsub(/[<>\x00-\x1f\x7f]/,'')[0,240]);@moderation_code=code;@expires_at=expires_at.is_a?(Integer) ? expires_at : 0
    end
  end
  module ModerationMessages
    class << self
      def receive(text);@pending=text.to_s;end
      def take;value=@pending;@pending=nil;value;end
      def update
        return unless @pending && $scene.is_a?(Scene_Map) && $game_temp &&
          !$game_temp.in_battle && !$game_temp.in_menu && !$game_temp.message_window_showing &&
          !Areas.active? && !Areas.busy? && !Areas.restoring?
        message=take
        pbMessage(message)
      end
    end
  end
  module ModeratedMapChannel
    def collect
      ticket=@worker
      if managed? && ticket && !ticket.alive?
        result=ticket.value
        raw=result.is_a?(Hash) && (result[:body] || result['body'])
        reply=JSON.parse(raw) if raw.is_a?(String) && raw.bytesize<=MAX_RESPONSE
        if reply.is_a?(Hash)
          @chat_muted_until=reply['chat_muted_until'] if reply['chat_muted_until'].is_a?(Integer)
          if reply['ok']==false && %w[CHAT_MUTED KICKED BANNED].include?(reply['code'])
            @worker=nil
            error=ModerationError.new(reply['code'],reply['error'],reply['until'])
            if error.moderation_code=='CHAT_MUTED'
              @outbox=nil;@sent_emote=nil;@chat_muted_until=error.expires_at
              @notice=error.message;@revision=revision+1
              NordelunaOnline.record_online_error(error,'chat_muted')
            else
              connection_failed(error)
            end
            return
          end
        end
      end
      super
    end

    def queue_message(text)
      if (@chat_muted_until || 0)>Time.now.to_i
        minutes=((@chat_muted_until-Time.now.to_i)/60.0).ceil
        raise Error,_INTL('Voce esta silenciado no chat. Aguarde cerca de {1} minuto(s).',minutes)
      end
      super
    end

    def connection_failed(error)
      terminal=error.is_a?(ModerationError) && %w[KICKED BANNED].include?(error.moderation_code)
      if terminal
        @desired=false;@token=@resume_token=nil;@outbox=nil
        ModerationMessages.receive(error.message)
      end
      result=super
      if terminal
        @desired=false;@connection_state=:disconnected;@notice=error.message
        # A heartbeat can be rejected while a battle owns the foreground.
        # Schedule the return now; Areas.update waits until the battle closes.
        Areas.connection_lost if Areas.active?
      end
      result
    end

    def connect(*args)
      @chat_muted_until=0
      super
    rescue ModerationError
      # The caller displays synchronous connection failures itself.
      ModerationMessages.take
      raise
    end
  end
  MapChannel.singleton_class.prepend(ModeratedMapChannel)
end
EventHandlers.add(:on_frame_update,:nordeluna_moderation_notice,proc { NordelunaOnline::ModerationMessages.update })
