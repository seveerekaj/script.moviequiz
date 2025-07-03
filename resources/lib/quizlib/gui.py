#
#      Copyright (C) 2013 Tommy Winther
#      http://tommy.winther.nu
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this Program; see the file LICENSE.txt.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html
#
import datetime
import os
import random
import re
import threading
import time

import buggalo
import xbmc
import xbmcgui

from . import game
from . import imdb, question
from . import library
from . import logger
from . import player
from .strings import *

RESOURCES_PATH = os.path.join(ADDON.getAddonInfo('path'), 'resources')
AUDIO_CORRECT = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'audio', 'correct.wav')
AUDIO_WRONG = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'audio', 'wrong.wav')
BACKGROUND_MOVIE = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'quiz-background-movie.jpg')
BACKGROUND_TV = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'quiz-background-tvshows.jpg')
BACKGROUND_THEME = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'quiz-background-theme.jpg')
NO_PHOTO_IMAGE = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'quiz-no-photo.png')

class MenuGui(xbmcgui.WindowXMLDialog):
    C_MENU_LIST = 4001
    C_INFO_TEXT = 6001

    ACTION_KEY = 'action'
    ACTION_MOVIE_QUIZ = 1
    ACTION_TV_QUIZ = 2
    ACTION_MUSIC_QUIZ = 3
    ACTION_DOWNLOAD_IMDB = 4
    ACTION_OPEN_SETTINGS = 5
    ACTION_EXIT = 6
    ACTION_ABOUT = 7

    def __new__(cls, quizGui):
        return super().__new__(cls, 'script-moviequiz-menu.xml', ADDON.getAddonInfo('path'))

    def __init__(self, quizGui):
        super().__init__()
        self.quizGui = quizGui
        self.moviesEnabled = True
        self.tvShowsEnabled = True
        self.musicEnabled = True

    @buggalo.buggalo_try_except()
    def onInit(self):
        movies = library.getMovies(['art']).limitTo(44).asList()
        posters = [movie['art']['poster'] for movie in movies if 'art' in movie and 'poster' in movie['art']]
        if posters:
            for idx in range(0, 44):
                self.getControl(1000 + idx).setImage(posters[idx % len(posters)])

        # Check preconditions
        self.validateSettings()

    def validateSettings(self):
        hasMovies = library.hasMovies()
        hasTVShows = library.hasTVShows()
        hasMusic = library.hasMusic()

        if not hasMovies and not hasTVShows and not hasMusic:
            self.close()
            self.quizGui.close()
            # Must have at least one movie or tvshow
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_HAS_NO_CONTENT))
            return

        if not library.isAnyVideosWatched() and ADDON.getSetting(SETT_ONLY_WATCHED_MOVIES) == 'true':
            # Only watched movies requires at least one watched video files
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_ONLY_WATCHED))
            ADDON.setSetting(SETT_ONLY_WATCHED_MOVIES, 'false')

        if not library.isAnyMPAARatingsAvailable() and ADDON.getSetting(SETT_MOVIE_RATING_LIMIT_ENABLED) == 'true':
            # MPAA rating requires ratings to be available in database
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_MOVIE_RATING_LIMIT))
            ADDON.setSetting(SETT_MOVIE_RATING_LIMIT_ENABLED, 'false')

        if not library.isAnyContentRatingsAvailable() and ADDON.getSetting(SETT_TVSHOW_RATING_LIMIT_ENABLED) == 'true':
            # Content rating requires ratings to be available in database
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_TVSHOW_RATING_LIMIT))
            ADDON.setSetting(SETT_TVSHOW_RATING_LIMIT_ENABLED, 'false')

        self.moviesEnabled = bool(hasMovies and question.isAnyMovieQuestionsEnabled())
        self.tvShowsEnabled = bool(hasTVShows and question.isAnyTVShowQuestionsEnabled())
        self.musicEnabled = bool(hasMusic and question.isAnyMusicQuestionsEnabled())

        if not question.isAnyMovieQuestionsEnabled():
            xbmcgui.Dialog().ok(strings(E_WARNING), strings(E_ALL_MOVIE_QUESTIONS_DISABLED, E_QUIZ_TYPE_NOT_AVAILABLE))

        if not question.isAnyTVShowQuestionsEnabled():
            xbmcgui.Dialog().ok(strings(E_WARNING), strings(E_ALL_TVSHOW_QUESTIONS_DISABLED, E_QUIZ_TYPE_NOT_AVAILABLE))

        self.updateMenu()

    @buggalo.buggalo_try_except()
    def onAction(self, action):
        if action.getId() in [xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_PARENT_DIR, xbmcgui.ACTION_NAV_BACK]:
            self.quizGui.close()
            self.close()
            return
        elif action.getId() in [xbmcgui.ACTION_MOVE_UP, xbmcgui.ACTION_MOVE_DOWN]: #todo: what about analog move down/up? and is there a better way to do this, perhaps onFocus for ListItem?
            item = self.getControl(MenuGui.C_MENU_LIST).getSelectedItem()
            action = int(item.getProperty(MenuGui.ACTION_KEY))
            if action == MenuGui.ACTION_ABOUT:
                self.getControl(MenuGui.C_INFO_TEXT).setText(strings(M_ABOUT_TEXT_BODY))
            elif action == MenuGui.ACTION_DOWNLOAD_IMDB:
                text = strings(M_DOWNLOAD_IMDB_INFO) % (strings(Q_WHAT_MOVIE_IS_THIS_QUOTE_FROM), strings(Q_WHAT_TVSHOW_IS_THIS_QUOTE_FROM))
                self.getControl(MenuGui.C_INFO_TEXT).setText(text)
            self.getControl(MenuGui.C_INFO_TEXT).setVisible(action == MenuGui.ACTION_ABOUT or action == MenuGui.ACTION_DOWNLOAD_IMDB)

    def _buildMenuItemsList(self, itemsToAdd):
        items = []
        for stringID, action in itemsToAdd:
            item = xbmcgui.ListItem(strings(stringID))
            item.setProperty(MenuGui.ACTION_KEY, str(action))
            items.append(item)
        return items

    def updateMenu(self):
        self.getControl(MenuGui.C_INFO_TEXT).setVisible(False)
        listControl = self.getControl(MenuGui.C_MENU_LIST)
        listControl.reset()
        items = [
            (M_SETTINGS, MenuGui.ACTION_OPEN_SETTINGS),
            (M_DOWNLOAD_IMDB, MenuGui.ACTION_DOWNLOAD_IMDB),
            (M_ABOUT, MenuGui.ACTION_ABOUT),
            (M_EXIT, MenuGui.ACTION_EXIT)
        ]
        if self.musicEnabled:
            items.insert(0, (M_PLAY_MUSIC_QUIZ, MenuGui.ACTION_MUSIC_QUIZ))
        if self.tvShowsEnabled:
            items.insert(0, (M_PLAY_TVSHOW_QUIZ, MenuGui.ACTION_TV_QUIZ))
        if self.moviesEnabled:
            items.insert(0, (M_PLAY_MOVIE_QUIZ, MenuGui.ACTION_MOVIE_QUIZ))

        listControl.addItems(self._buildMenuItemsList(items))
        self.setFocus(listControl)

    @buggalo.buggalo_try_except()
    def onClick(self, controlId):
        """
        @param controlId: id of the control that was clicked
        @type controlId: int
        """
        if controlId == MenuGui.C_MENU_LIST:
            item = self.getControl(MenuGui.C_MENU_LIST).getSelectedItem()
            action = int(item.getProperty(MenuGui.ACTION_KEY))

            if action == MenuGui.ACTION_MOVIE_QUIZ or action == MenuGui.ACTION_TV_QUIZ or action == MenuGui.ACTION_MUSIC_QUIZ:
                actionToQuizTypeDict = {
                    MenuGui.ACTION_MOVIE_QUIZ: game.GAMETYPE_MOVIE,
                    MenuGui.ACTION_TV_QUIZ: game.GAMETYPE_TVSHOW,
                    MenuGui.ACTION_MUSIC_QUIZ: game.GAMETYPE_MUSIC
                }
                gameInstance = game.UnlimitedGame(actionToQuizTypeDict[action])
                self.close()
                self.quizGui.newGame(gameInstance)
                return
            elif action == MenuGui.ACTION_DOWNLOAD_IMDB:
                imdb.downloadData()
                # force a quit/reopen as quotes are only loaded once in QuizGui.onInit
                self.quizGui.close()
                self.close()
                return
            elif action == MenuGui.ACTION_OPEN_SETTINGS:
                ADDON.openSettings()
                self.validateSettings()
                self.quizGui.onSettingsChanged()
            elif action == MenuGui.ACTION_EXIT:
                self.quizGui.close()
                self.close()
                return

class QuizGui(xbmcgui.WindowXML):
    C_MAIN_FIRST_ANSWER = 4000
    C_MAIN_LAST_ANSWER = 4003
    C_MAIN_FIRST_ANSWER_COVER_IMAGE = 4010
    C_MAIN_REPLAY = 4301
    C_MAIN_EXIT = 4302
    C_MAIN_LOADING = 4020
    C_MAIN_QUESTION_LABEL = 4300
    C_MAIN_PHOTO = 4400
    C_MAIN_MOVIE_BACKGROUND = 4500
    C_MAIN_TVSHOW_BACKGROUND = 4501
    C_MAIN_QUOTE_LABEL = 4600
    C_MAIN_PHOTO_1 = 4701
    C_MAIN_PHOTO_2 = 4702
    C_MAIN_PHOTO_3 = 4703
    C_MAIN_PHOTO_LABEL_1 = 4711
    C_MAIN_PHOTO_LABEL_2 = 4712
    C_MAIN_PHOTO_LABEL_3 = 4713
    C_MAIN_VIDEO_FILE_NOT_FOUND = 4800
    C_MAIN_VIDEO_VISIBILITY = 5000
    C_MAIN_VIDEO_FULLSCREEN_VISIBILITY = 5007
    C_MAIN_PHOTO_VISIBILITY = 5001
    C_MAIN_QUOTE_VISIBILITY = 5004
    C_MAIN_THREE_PHOTOS_VISIBILITY = 5006
    C_MAIN_CORRECT_VISIBILITY = 5002
    C_MAIN_INCORRECT_VISIBILITY = 5003
    C_MAIN_LOADING_VISIBILITY = 5005

    STATE_SPLASH = 1
    STATE_LOADING = 2
    STATE_PLAYING = 3
    STATE_GAME_OVER = 4

    def __new__(cls):
        return super().__new__(cls, 'script-moviequiz-main.xml', ADDON.getAddonInfo('path'))

    def __init__(self):
        super().__init__()
        self.gameInstance = None
        self.player = None
        self.questionCandidates = []
        self.defaultLibraryFilters = []
        self.question = None
        self.previousQuestions = []
        self.lastClickTime = -1
        self.delayedNewQuestionTimer = None
        self.uiState = self.STATE_SPLASH

    def onSettingsChanged(self):
        minPercent = ADDON.getSettingInt('video.player.min_percent')
        maxPercent = ADDON.getSettingInt('video.player.max_percent')
        duration = ADDON.getSettingInt('video.player.duration')
        self.getControl(self.C_MAIN_VIDEO_FULLSCREEN_VISIBILITY).setVisible(ADDON.getSettingBool('video.fullscreen.enabled'))
        if self.player is None:
            self.player = player.TimeLimitedPlayer(min(minPercent, maxPercent), max(minPercent, maxPercent), duration)
        else:
            # note: I could create a new instance of self.player with the new parameters here, but when I tried that, weird stuff happened -
            # the player's threading timer was getting called twice: with both old and new duration. I also tried "del self.player" before creating a new player,
            # but the destructor was never actually invoked. So I just use the setBounds function on the existing player instead of creating a new one
            logger.log(f"setting new player with min:{minPercent} max:{maxPercent}, duration:{duration}")
            self.player.setBounds(min(minPercent, maxPercent), max(minPercent, maxPercent), duration)

    @buggalo.buggalo_try_except()
    def onInit(self):
        self.onSettingsChanged()
        self.getControl(2).setVisible(False)
        startTime = datetime.datetime.now()
        question.IMDB.loadData()
        delta = datetime.datetime.now() - startTime
        if delta.seconds < 2:
            xbmc.sleep(1000 * (2 - delta.seconds))
        self.showMenuDialog()

    def showMenuDialog(self):
        menuGui = MenuGui(self)
        menuGui.doModal()
        del menuGui

    def newGame(self, gameInstance):
        self.getControl(1).setVisible(False)
        self.getControl(2).setVisible(True)

        self.gameInstance = gameInstance
        logger.log("Starting game: %s" % str(self.gameInstance))

        if self.gameInstance.getType() == game.GAMETYPE_TVSHOW:
            self.defaultBackground = BACKGROUND_TV
        else:
            self.defaultBackground = BACKGROUND_MOVIE
        self.getControl(self.C_MAIN_MOVIE_BACKGROUND).setImage(self.defaultBackground)

        self.defaultLibraryFilters = list()
        if gameInstance.getType() == game.GAMETYPE_MOVIE and ADDON.getSetting('movie.rating.limit.enabled') == 'true':
            self.defaultLibraryFilters.extend(library.buildRatingsFilters(ADDON.getSetting('movie.rating.limit')))

        elif gameInstance.getType() == game.GAMETYPE_TVSHOW and ADDON.getSetting('tvshow.rating.limit.enabled') == 'true':
            self.defaultLibraryFilters.extend(library.buildRatingsFilters(ADDON.getSetting('tvshow.rating.limit')))

        if ADDON.getSetting(SETT_ONLY_WATCHED_MOVIES) == 'true':
            self.defaultLibraryFilters.extend(library.buildOnlyWatchedFilter())

        self.questionCandidates = question.getEnabledQuestionCandidates(self.gameInstance)

        self.question = None
        self.previousQuestions = []
        self.uiState = self.STATE_LOADING

        self.onNewQuestion()

    def close(self):
        if self.player and self.player.isPlaying():
            self.player.stopPlayback(True)
        super().close()

    @buggalo.buggalo_try_except()
    def onAction(self, action):
        if self.uiState == self.STATE_SPLASH and action.getId() in [xbmcgui.ACTION_PARENT_DIR, xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK]:
            self.close()
            return

        if action.getId() in [xbmcgui.ACTION_PARENT_DIR, xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK]:
            self.onGameOver()

        if self.uiState == self.STATE_LOADING:
            return
        elif action.getId() in [xbmcgui.REMOTE_1]:
            self.setFocusId(self.C_MAIN_FIRST_ANSWER)
            self.onQuestionAnswered(self.question.getAnswer(0))
        elif action.getId() in [xbmcgui.REMOTE_2, xbmcgui.ACTION_JUMP_SMS2]:
            self.setFocusId(self.C_MAIN_FIRST_ANSWER + 1)
            self.onQuestionAnswered(self.question.getAnswer(1))
        elif action.getId() in [xbmcgui.REMOTE_3, xbmcgui.ACTION_JUMP_SMS3]:
            self.setFocusId(self.C_MAIN_FIRST_ANSWER + 2)
            self.onQuestionAnswered(self.question.getAnswer(2))
        elif action.getId() in [xbmcgui.REMOTE_4, xbmcgui.ACTION_JUMP_SMS4]:
            self.setFocusId(self.C_MAIN_FIRST_ANSWER + 3)
            self.onQuestionAnswered(self.question.getAnswer(3))

    @buggalo.buggalo_try_except()
    def onClick(self, controlId):
        difference = time.time() - self.lastClickTime
        self.lastClickTime = time.time()
        if difference < 0.7:
            logger.log("Ignoring key-repeat onClick")
            return

        elif controlId == self.C_MAIN_EXIT:
            self.onGameOver()
        elif self.uiState == self.STATE_LOADING:
            return  # ignore the rest while we are loading
        elif self.question and (self.C_MAIN_FIRST_ANSWER <= controlId <= self.C_MAIN_LAST_ANSWER):
            answer = self.question.getAnswer(controlId - self.C_MAIN_FIRST_ANSWER)
            self.onQuestionAnswered(answer)
        elif controlId == self.C_MAIN_REPLAY:
            self.player.replay()

    @buggalo.buggalo_try_except()
    def onFocus(self, controlId):
        pass

    def onGameOver(self):
        if self.uiState == self.STATE_GAME_OVER:
            return # ignore multiple invocations
        self.uiState = self.STATE_GAME_OVER

        if self.delayedNewQuestionTimer is not None:
            self.delayedNewQuestionTimer.cancel()

        if self.player.isPlaying():
            self.player.stopPlayback(True)
        self.showMenuDialog()

    @buggalo.buggalo_try_except()
    def onNewQuestion(self):
        self.delayedNewQuestionTimer = None
        self.uiState = self.STATE_LOADING
        self.getControl(self.C_MAIN_LOADING_VISIBILITY).setVisible(True)
        self.question = self._getNewQuestion()
        if not self.question:
            self.onGameOver()
            return
        self.getControl(self.C_MAIN_QUESTION_LABEL).setLabel(self.question.getText())

        answers = self.question.getAnswers()
        for idx in range(0, 4):
            button = self.getControl(self.C_MAIN_FIRST_ANSWER + idx)
            if idx >= len(answers):
                button.setLabel('')
                button.setVisible(False)
            else:
                button.setLabel(answers[idx].text, textColor='0xFFFFFFFF')
                button.setVisible(True)
                coverImage = self.getControl(self.C_MAIN_FIRST_ANSWER_COVER_IMAGE + idx)
                if answers[idx].coverFile is not None:
                    coverImage.setImage(answers[idx].coverFile)
                else:
                    coverImage.setImage(NO_PHOTO_IMAGE)

        displayType = self.question.getDisplayType()
        if self.question.getFanartFile():
            self.getControl(self.C_MAIN_MOVIE_BACKGROUND).setImage(self.question.getFanartFile())
        elif isinstance(displayType, question.AudioDisplayType):
            self.getControl(self.C_MAIN_MOVIE_BACKGROUND).setImage(BACKGROUND_THEME)
        else:
            self.getControl(self.C_MAIN_MOVIE_BACKGROUND).setImage(self.defaultBackground)

        if isinstance(displayType, question.VideoDisplayType):
            self.getControl(self.C_MAIN_VIDEO_FILE_NOT_FOUND).setVisible(False)
            xbmc.sleep(1000)  # give skin animation time to execute
            if not self.player.playWindowed(displayType.getVideoFile()):
                self.getControl(self.C_MAIN_VIDEO_FILE_NOT_FOUND).setVisible(True)

        elif isinstance(displayType, question.PhotoDisplayType):
            self.getControl(self.C_MAIN_PHOTO).setImage(displayType.getPhotoFile())

        elif isinstance(displayType, question.ThreePhotoDisplayType):
            self.getControl(self.C_MAIN_PHOTO_1).setImage(displayType.getPhotoFile(0)[0])
            self.getControl(self.C_MAIN_PHOTO_LABEL_1).setLabel(displayType.getPhotoFile(0)[1])
            self.getControl(self.C_MAIN_PHOTO_2).setImage(displayType.getPhotoFile(1)[0])
            self.getControl(self.C_MAIN_PHOTO_LABEL_2).setLabel(displayType.getPhotoFile(1)[1])
            self.getControl(self.C_MAIN_PHOTO_3).setImage(displayType.getPhotoFile(2)[0])
            self.getControl(self.C_MAIN_PHOTO_LABEL_3).setLabel(displayType.getPhotoFile(2)[1])

        elif isinstance(displayType, question.QuoteDisplayType):
            quoteText = displayType.getQuoteText()
            quoteText = self._obfuscateQuote(quoteText)
            self.getControl(self.C_MAIN_QUOTE_LABEL).setText(quoteText)

        elif isinstance(displayType, question.AudioDisplayType):
            #self.player.playAudio(displayType.getAudioFile())
            self.player.playWindowed(displayType.getAudioFile())

        self.onVisibilityChanged(displayType)

        self.uiState = self.STATE_PLAYING
        self.getControl(self.C_MAIN_LOADING_VISIBILITY).setVisible(False)

    def _getNewQuestion(self):
        retries = 0
        q = None
        while retries < 100 and self.uiState == self.STATE_LOADING:
            xbmc.sleep(10)  # give XBMC time to process other events
            retries += 1

            self.getControl(self.C_MAIN_LOADING).setPercent(retries)

            random.seed()
            random.shuffle(self.questionCandidates)
            for candidate in self.questionCandidates:
                try:
                    q = candidate(self.defaultLibraryFilters)
                    break
                except question.QuestionException as ex:
                    pass
                    # print("QuestionException: %s" % str(ex))
                except Exception as ex:
                    logger.log("%s in %s" % (ex.__class__.__name__, candidate.__name__))
                    import traceback
                    import sys

                    traceback.print_exc(file=sys.stdout)

            if q is None or len(q.getAnswers()) < 3:
                continue

            # print(type(q))
            if not q.getUniqueIdentifier() in self.previousQuestions:
                self.previousQuestions.append(q.getUniqueIdentifier())
                break

        return q

    def onQuestionAnswered(self, answer):
        """
        @param answer: the chosen answer by the user
        @type answer: Answer
        """
        logger.log("onQuestionAnswered(..)")

        if self.player.isPlaying():
            self.player.stopPlayback()

        if answer is not None and answer.correct:
            xbmc.playSFX(AUDIO_CORRECT)
            self.getControl(self.C_MAIN_CORRECT_VISIBILITY).setVisible(False)
        else:
            xbmc.playSFX(AUDIO_WRONG)
            self.getControl(self.C_MAIN_INCORRECT_VISIBILITY).setVisible(False)
        threading.Timer(0.5, self.onQuestionAnswerFeedbackTimer).start()

        # show correct answers if setting enabled and if user answered incorrectly or the question type is quote
        # it's nice to see non-obfuscated quote even when answered correctly
        if ADDON.getSetting('show.correct.answer') == 'true' and (not answer.correct or isinstance(self.question.getDisplayType(), question.QuoteDisplayType)):
            if not answer.correct:
                for idx, answerIter in enumerate(self.question.getAnswers()):
                    if answerIter.correct:
                        self.getControl(self.C_MAIN_FIRST_ANSWER + idx).setLabel('[B]%s[/B]' % answerIter.text)
                        self.setFocusId(self.C_MAIN_FIRST_ANSWER + idx)
                    else:
                        self.getControl(self.C_MAIN_FIRST_ANSWER + idx).setLabel(textColor='0x88888888')

            if isinstance(self.question.getDisplayType(), question.QuoteDisplayType):
                # Display non-obfuscated quote text
                self.getControl(self.C_MAIN_QUOTE_LABEL).setText(self.question.getDisplayType().getQuoteText())

            if self.uiState != self.STATE_GAME_OVER:
                self.delayedNewQuestionTimer = threading.Timer(2, self.onNewQuestion)
                self.delayedNewQuestionTimer.start()

        else:
            self.onNewQuestion()

    @buggalo.buggalo_try_except()
    def onQuestionAnswerFeedbackTimer(self):
        """
        onQuestionAnswerFeedbackTimer is invoked by a timer when the red or green background behind the answers box
        must be faded out and hidden.

        Note: Visibility is inverted in skin
        """
        self.getControl(self.C_MAIN_CORRECT_VISIBILITY).setVisible(True)
        self.getControl(self.C_MAIN_INCORRECT_VISIBILITY).setVisible(True)

    def onVisibilityChanged(self, displayType=None):
        """
        @type displayType: quizlib.question.DisplayType
        @param displayType: the type of display required by the current question
        """
        self.getControl(self.C_MAIN_VIDEO_VISIBILITY).setVisible(not isinstance(displayType, question.VideoDisplayType))
        self.getControl(self.C_MAIN_PHOTO_VISIBILITY).setVisible(not isinstance(displayType, question.PhotoDisplayType))
        self.getControl(self.C_MAIN_QUOTE_VISIBILITY).setVisible(not isinstance(displayType, question.QuoteDisplayType))
        self.getControl(self.C_MAIN_THREE_PHOTOS_VISIBILITY).setVisible(not isinstance(displayType, question.ThreePhotoDisplayType))

    def _obfuscateQuote(self, quote):
        names = list()

        for m in re.finditer('(\[.*?\])', quote, re.DOTALL):
            quote = quote.replace(m.group(1), '')

        for m in re.finditer('(.*?:)', quote):
            name = m.group(1)
            if not name in names:
                names.append(name)

        for idx, name in enumerate(names):
            repl = '#%d:' % (idx + 1)
            quote = quote.replace(name, repl)

        return quote
