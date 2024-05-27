import xbmc
import xbmcaddon

def log(message, level=xbmc.LOGDEBUG):
    xbmc.log("script.moviequiz >> " + message, level)
    
def notification(message, duration=2000):
    icon = xbmcaddon.Addon().getAddonInfo('icon')
    xbmc.executebuiltin('Notification(MovieQuiz, %s, %d, %s)'%(message, duration, icon))
