module NordelunaOnline
  module Matchmaking
    class << self
      def api(action,data={})
        NordelunaOnline.request(NordelunaOnline.server,data.merge('action'=>action,'account'=>Identity.ensure_registered))
      end
      def search
        Friends.busy('busy') { run_search }
      end
      def run_search
        health=NordelunaOnline.test_connection(false)
        raise VersionMismatch,'Busca automatica precisa do servidor revisao 9.' unless health['revision'].to_i>=9
        Identity.ensure_registered
        rule=NordelunaOnline.choose_room_rules
        return unless rule
        payload=NordelunaOnline.select_online_team(rule)
        return unless payload
        old_menu=$game_temp.in_menu
        $game_temp.in_menu=true
        MapChannel.suspend
        suspended=true
        reply=api('match_enter','profile'=>NordelunaOnline.profile,'payload'=>payload,'rules'=>rule,'build'=>NordelunaOnline.build)
        ticket=reply['ticket'];next_poll=NordelunaOnline.now+2
        left,top,width,height=OnlineUI.bounds(2)
        screen=ChatPanel.create_sprite(width,height);screen.x,screen.y=left,top
        OnlineUI.draw_background(screen.bitmap,width,height)
        ChatPanel.text(screen.bitmap,'Procurando batalha...',18,18,width-36,20,OnlineUI.color(:ACCENT))
        ChatPanel.text(screen.bitmap,'Mesma versao e mesmas regras',18,62,width-36,14)
        ChatPanel.text(screen.bitmap,'Voltar: cancelar a busca',18,104,width-36,14)
        while reply['state']=='waiting'
          NordelunaOnline.frame
          return if Input.trigger?(Input::BACK)
          if NordelunaOnline.now>=next_poll
            reply=api('match_poll','ticket'=>ticket)
            next_poll=NordelunaOnline.now+2
          end
        end
        raise Error,'A busca foi cancelada. Tente novamente.' unless reply['state']=='matched'
        ChatPanel.dispose_sprite(screen);screen=nil
        room=reply['room']
        raise VersionMismatch,'As regras da busca mudaram.' unless room['rules']==rule
        raise Error,'Foi encontrada uma busca anterior com outra equipe. Inicie novamente.' unless room['players'][room['side']]['payload']==payload
        session=Session.new(NordelunaOnline.server,room);session.rules=rule
        Friends.busy('battle') { NordelunaOnline.start_battle(session,room) }
      rescue Error => error
        pbMessage(_INTL('Busca: {1}',error.message))
      ensure
        ChatPanel.dispose_sprite(screen)
        if session
          session.call('cancel') rescue nil
        elsif ticket
          api('match_cancel','ticket'=>ticket) rescue nil
        end
        $game_temp.in_menu=old_menu unless old_menu.nil?
        MapChannel.resume if suspended
      end
    end
  end
end
