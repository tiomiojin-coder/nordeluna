module NordelunaOnline
  # Local map events. Networking, team selection, trades and their save protocol
  # remain in the existing online implementation.
  module SocialMaps
    MAPS = [39, 40, 41].freeze
    PHASE_NAMES = ["Lua Nova", "Lua Crescente", "Lua Cheia", "Lua Minguante"].freeze
    PUZZLE_EVENT = 30
    class << self
      def call(action, *args)
        raise Error, "Esta interacao pertence a Praca, ao Coliseu ou ao Mercado." unless MAPS.include?($game_map.map_id)
        send(action, *args)
      rescue Cancelled
        false
      rescue StandardError => error
        NordelunaOnline.record_online_error(error, "social_map_#{action}")
        pbMessage(_INTL("Nao foi possivel concluir esta interacao: {1}", error.message))
        false
      end

      def reception
        n = pbMessage(_INTL("Bem-vindo a Praca Central, {1}! O que procura?", NordelunaOnline.nickname),
          [_INTL("Conhecer a praca"), _INTL("Alterar meu nick"), _INTL("Jogadores proximos"), _INTL("Voltar a campanha"), _INTL("Sair")], 5)
        case n
        when 0 then directions
        when 1 then NordelunaOnline.configure_nickname
        when 2 then Ghosts.interact
        when 3 then leave
        end
      end

      def directions
        pbMessage(_INTL("A oeste fica o Coliseu Lunar; a leste, o Mercado Global. Ao sul, o Jardim das Fases e a Alameda dos Encontros."))
        pbMessage(_INTL("A Fonte Lunar marca o centro. Converse com os treinadores e examine as placas. A recepcao permite voltar ao ponto salvo da campanha."))
      end

      def door(map, x, y, direction)
        point = {"map"=>map, "x"=>x, "y"=>y, "direction"=>direction}
        if Areas.active?
          unless Areas.online_map?(map)
            pbMessage(_INTL("Este interior esta pronto no projeto, mas ainda precisa ser habilitado na configuracao do cliente e do servidor online."))
            return false
          end
          Areas.authorize(map)
          Areas.transfer(point)
          true
        elsif $DEBUG
          # Explicit editor playtest; no account, room or campaign anchor is made.
          Areas.transfer(point)
          true
        else
          pbMessage(_INTL("Entre nas areas online pela opcao Sala e chat do menu Online."))
          false
        end
      end

      def leave
        unless Areas.active?
          pbMessage(_INTL("Esta e uma visita local de teste. O retorno online fica disponivel ao entrar pela opcao Sala e chat."))
          return false
        end
        return false unless pbConfirmMessage(_INTL("Sair da Praca e voltar ao ponto salvo da campanha?"))
        MapChannel.disconnect
        true
      end

      def battle_desk
        n = pbMessage(_INTL("Coliseu Lunar: a batalha comeca somente depois das confirmacoes dos dois treinadores."),
          [_INTL("Criar sala de batalha"), _INTL("Entrar com codigo"), _INTL("Como funcionam as regras?"), _INTL("Sair")], 4)
        case n
        when 0 then NordelunaOnline.connect("battle", false)
        when 1 then NordelunaOnline.connect("battle", true)
        when 2
          pbMessage(_INTL("Quem cria escolhe nivel, quantidade, lendarios e formato simples ou duplo. Cada jogador escolhe a propria equipe; as alteracoes da batalha usam copias dos Pokemon."))
        end
      end

      def trade_desk
        n = pbMessage(_INTL("Central de Trocas: combine a troca com outro treinador e compartilhe o codigo da sala."),
          [_INTL("Criar sala de troca"), _INTL("Entrar com codigo"), _INTL("Seguranca da troca"), _INTL("Sair")], 4)
        case n
        when 0 then NordelunaOnline.connect("trade", false)
        when 1 then NordelunaOnline.connect("trade", true)
        when 2
          pbMessage(_INTL("Confira os dois Pokemon na tela de confirmacao. A troca usa o sistema de comprovante e recuperacao do Online, com gravacao do save ao concluir."))
          pbMessage(_INTL("Este balcao realiza trocas diretas por sala. Nao anuncia ou entrega Pokemon automaticamente."))
        end
      end

      def heal
        return false unless pbConfirmMessage(_INTL("Descansar e recuperar sua equipe? Seu ponto de retorno da campanha sera mantido."))
        $player.party.each { |pokemon| pokemon.heal unless pokemon.egg? }
        pbMessage(_INTL("Sua equipe esta recuperada. Boa exploracao!"))
        true
      end

      def team_info
        usable = $player.party.reject(&:egg?)
        conscious = usable.count { |pokemon| !pokemon.fainted? }
        pbMessage(_INTL("Voce trouxe {1} Pokemon e {2} estao aptos a batalhar. A quantidade elegivel tambem depende das regras de cada sala.", usable.length, conscious))
        pbMessage(_INTL("Para duplas, leve ao menos dois Pokemon elegiveis. Confira golpes, itens e habilidades antes de confirmar a equipe."))
      end

      def partner_story
        pokemon = $player.party.find { |entry| !entry.egg? }
        return pbMessage(_INTL("A praca acolhe treinadores de todas as regioes.")) unless pokemon
        if pokemon.shiny?
          pbMessage(_INTL("O brilho de {1} combina com a Fonte Lunar. Aqui cada parceiro tem a propria historia!", pokemon.name))
        else
          pbMessage(_INTL("{1} parece observar os encontros da praca. Nem toda jornada precisa terminar em uma batalha.", pokemon.name))
        end
      end

      def emote_lesson
        n = pbMessage(_INTL("Quer cumprimentar quem esta na mesma area e instancia?"),
          [_INTL("Acenar"), _INTL("Comemorar"), _INTL("Chamar para batalha"), _INTL("Sair")], 4)
        return if n < 0 || n > 2
        unless MapChannel.active?
          pbMessage(_INTL("Entre numa sala online para enviar um emote aos outros treinadores."))
          return false
        end
        MapChannel.send_emote(%w[wave celebrate battle][n])
        true
      end

      def phase_stone(index)
        raise Error, "Pedestal lunar invalido." unless index.is_a?(Integer) && index.between?(0, 3)
        key = proc { |letter| [39, PUZZLE_EVENT, letter] }
        if $game_self_switches[key.call("D")]
          pbMessage(_INTL("O Jardim das Fases recorda sua visita: o ciclo se completa e sempre recomeça."))
          return
        end
        expected = %w[A B C].count { |letter| $game_self_switches[key.call(letter)] }
        pbMessage(_INTL("Pedestal da {1}.", PHASE_NAMES[index]))
        return unless pbConfirmMessage(_INTL("Tocar este pedestal?"))
        if index == expected
          $game_self_switches[key.call(%w[A B C D][index])] = true
          if index == 3
            pbMessage(_INTL("Os quatro pedestais ressoam: nova, crescente, cheia e minguante. Na pedra surge uma frase:"))
            pbMessage(_INTL("\"Quem compartilha o caminho nunca viaja sob um ceu vazio.\" Voce desvendou o Jardim das Fases!"))
          else
            pbMessage(_INTL("Um brilho discreto indica que o ciclo continua."))
          end
        else
          %w[A B C].each { |letter| $game_self_switches[key.call(letter)] = false }
          pbMessage(_INTL("O brilho se apaga. A inscricao sugere comecar pela lua que ainda nao aparece no ceu."))
        end
        $game_map.need_refresh = true
      end

      def local_shop
        stock = [:POKEBALL, :GREATBALL, :POTION, :SUPERPOTION, :ANTIDOTE, :PARALYZEHEAL]
        stock.select! { |id| GameData::Item.try_get(id) }
        pbPokemonMart(stock, _INTL("Itens de viagem para quem passa pelo Mercado Global."))
      end

      def pc
        pbPokeCenterPC
      end

      def moon_clock
        hour = Time.now.hour
        message = hour.between?(6, 17) ?
          "Mesmo de dia, o desenho da lua permanece no piso. Os encontros da praca nao dependem do anoitecer." :
          "A noite transforma a praca num ponto de encontro. A Fonte Lunar indica o caminho de volta ao centro."
        pbMessage(_INTL(message))
      end
    end
  end
end
