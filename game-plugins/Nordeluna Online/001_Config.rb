# Shared by the Windows game and the Android port.
module NordelunaOnline
  VERSION = "0.6.0"
  PROTOCOL = 1
  BUILD = "nordeluna-online-2026-11-07-2"
  DEFAULT_SERVER = "https://nordeluna-online.discloud.dev"
  REQUEST_TIMEOUT = 12
  WAIT_TIMEOUT = 300
  POLL_INTERVAL = 0.7
  MAX_RESPONSE = 524288
  class Error < StandardError; end
  class Cancelled < Error; end
end

class PokemonGlobalMetadata
  attr_accessor :nordeluna_online_server
  attr_accessor :nordeluna_online_pending
end
