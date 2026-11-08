module NordelunaAtmosphere
  module PerformanceState
    def state
      result=super
      return result unless defined?(NordelunaPerformance)
      result=result.dup
      result[:count]=NordelunaPerformance.particles(result[:count])
      decoration=NordelunaPerformance.level(:decorations)
      if decoration==0
        result[:fog]=result[:warm]=result[:rays]=0
      elsif decoration==1
        result[:fog]=(result[:fog]*0.5).round
        result[:rays]=0
      end
      result
    end
  end
  singleton_class.prepend(PerformanceState)
end
