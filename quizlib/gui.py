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
import random

import threading
import os
import re
import time
import datetime

import xbmc
import xbmcgui
import xbmcvfs

from quizlib import game
from quizlib import question
from quizlib import player
from quizlib import library
from quizlib import imdb
from quizlib import logger

import buggalo

from quizlib.strings import *

# Constants from [xbmc]/xbmc/guilib/Key.h
ACTION_SELECT_ITEM = 7
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10

ACTION_REMOTE0 = 58
ACTION_REMOTE1 = 59
ACTION_REMOTE2 = 60
ACTION_REMOTE3 = 61
ACTION_REMOTE4 = 62
ACTION_REMOTE5 = 63
ACTION_REMOTE6 = 64
ACTION_REMOTE7 = 65
ACTION_REMOTE8 = 66
ACTION_REMOTE9 = 67

ACTION_NAV_BACK = 92

ACTION_JUMP_SMS2 = 142
ACTION_JUMP_SMS3 = 143
ACTION_JUMP_SMS4 = 144
ACTION_JUMP_SMS5 = 145
ACTION_JUMP_SMS6 = 146
ACTION_JUMP_SMS7 = 147
ACTION_JUMP_SMS8 = 148
ACTION_JUMP_SMS9 = 149

RESOURCES_PATH = os.path.join(ADDON.getAddonInfo('path'), 'resources')
AUDIO_CORRECT = os.path.join(RESOURCES_PATH, 'audio', 'correct.wav')
AUDIO_WRONG = os.path.join(RESOURCES_PATH, 'audio', 'wrong.wav')
BACKGROUND_MOVIE = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'quiz-background-movie.jpg')
BACKGROUND_TV = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'quiz-background-tvshows.jpg')
BACKGROUND_THEME = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'quiz-background-theme.jpg')
NO_PHOTO_IMAGE = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'quiz-no-photo.png')

MPAA_RATINGS = ['R', 'Rated R', 'PG-13', 'Rated PG-13', 'PG', 'Rated PG', 'G', 'Rated G']
CONTENT_RATINGS = ['TV-MA', 'TV-14', 'TV-PG', 'TV-G', 'TV-Y7-FV', 'TV-Y7', 'TV-Y']


class MenuGui(xbmcgui.WindowXMLDialog):
    C_MENU_VISIBILITY = 4000
    C_MENU_LIST = 4001
    C_MENU_ABOUT_VISIBILITY = 6000
    C_MENU_ABOUT_TEXT = 6001

    STATE_MAIN = 1
    STATE_MOVIE_QUIZ = 2
    STATE_TV_QUIZ = 3
    STATE_MUSIC_QUIZ = 11
    STATE_ABOUT = 5
    STATE_DOWNLOAD_IMDB = 6
    STATE_OPEN_SETTINGS = 7
    STATE_EXIT = 99

    def __new__(cls, quizGui):
        return super().__new__(cls, 'script-moviequiz-menu.xml', ADDON.getAddonInfo('path'))

    def __init__(self, quizGui):
        super().__init__()
        self.quizGui = quizGui
        self.state = MenuGui.STATE_MAIN
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
        hasMovies = library.hasMovies()
        hasTVShows = library.hasTVShows()
        hasMusic = library.hasMusic()

        if not hasMovies and not hasTVShows and not hasMusic:
            self.close()
            self.quizGui.close()
            # Must have at least one movie or tvshow
            # todo: anywhere we are calling dialog().ok with strings concated together, figure out how to separate with space or new line.
            # todo: why are strings separated into fragments the first place?
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_REQUIREMENTS_MISSING_LINE1) +
                                strings(E_REQUIREMENTS_MISSING_LINE2) + strings(E_REQUIREMENTS_MISSING_LINE3))
            return

        if not library.isAnyVideosWatched() and ADDON.getSetting(SETT_ONLY_WATCHED_MOVIES) == 'true':
            # Only watched movies requires at least one watched video files
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_ONLY_WATCHED_LINE1) +
                                strings(E_ONLY_WATCHED_LINE2) + strings(E_ONLY_WATCHED_LINE3))
            ADDON.setSetting(SETT_ONLY_WATCHED_MOVIES, 'false')

        if not library.isAnyMPAARatingsAvailable() and ADDON.getSetting(SETT_MOVIE_RATING_LIMIT_ENABLED) == 'true':
            # MPAA rating requires ratings to be available in database
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_MOVIE_RATING_LIMIT_LINE1) +
                                strings(E_MOVIE_RATING_LIMIT_LINE2) + strings(E_MOVIE_RATING_LIMIT_LINE3))
            ADDON.setSetting(SETT_MOVIE_RATING_LIMIT_ENABLED, 'false')

        if not library.isAnyContentRatingsAvailable() and ADDON.getSetting(SETT_TVSHOW_RATING_LIMIT_ENABLED) == 'true':
            # Content rating requires ratings to be available in database
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_TVSHOW_RATING_LIMIT_LINE1) +
                                strings(E_TVSHOW_RATING_LIMIT_LINE2) + strings(E_TVSHOW_RATING_LIMIT_LINE3))
            ADDON.setSetting(SETT_TVSHOW_RATING_LIMIT_ENABLED, 'false')

        self.moviesEnabled = bool(hasMovies and question.isAnyMovieQuestionsEnabled())
        self.tvShowsEnabled = bool(hasTVShows and question.isAnyTVShowQuestionsEnabled())
        self.musicEnabled = bool(hasMusic) and question.isAnyMusicQuestionsEnabled()

        if not question.isAnyMovieQuestionsEnabled():
            xbmcgui.Dialog().ok(strings(E_WARNING), strings(E_ALL_MOVIE_QUESTIONS_DISABLED) +
                                strings(E_QUIZ_TYPE_NOT_AVAILABLE))

        # if not question.isAnyTVShowQuestionsEnabled():
        #     xbmcgui.Dialog().ok(strings(E_WARNING), strings(E_ALL_TVSHOW_QUESTIONS_DISABLED) +
        #                         strings(E_QUIZ_TYPE_NOT_AVAILABLE))

        self.updateMenu()
        self.getControl(MenuGui.C_MENU_VISIBILITY).setVisible(False)

    def close(self):
        # hide menus
        # I think this causes the exit animation to happen?
        self.getControl(MenuGui.C_MENU_VISIBILITY).setVisible(True)
        self.getControl(MenuGui.C_MENU_ABOUT_VISIBILITY).setVisible(True)
        super().close()

    @buggalo.buggalo_try_except()
    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK]:
            self.getControl(MenuGui.C_MENU_VISIBILITY).setVisible(True)
            self.getControl(MenuGui.C_MENU_ABOUT_VISIBILITY).setVisible(True)
            xbmc.sleep(350)

            if self.state == MenuGui.STATE_MAIN:
                self.quizGui.close()
                self.close()
                return
            elif self.state in [MenuGui.STATE_ABOUT]:
                self.state = MenuGui.STATE_MAIN
                self.updateMenu()

            self.getControl(MenuGui.C_MENU_VISIBILITY).setVisible(False)

        #elif action.getId() ==

    def _buildMenuItemsList(self, itemsToAdd):
        items = []
        for stringID, state in itemsToAdd:
            item = xbmcgui.ListItem(strings(stringID))
            item.setProperty('state', str(state))
            items.append(item)
        return items

    def updateMenu(self):
        listControl = self.getControl(MenuGui.C_MENU_LIST)
        listControl.reset()
        if self.state == MenuGui.STATE_MAIN:
            items = [
                (30801, MenuGui.STATE_ABOUT),
                (30519, MenuGui.STATE_DOWNLOAD_IMDB),
                (30806, MenuGui.STATE_OPEN_SETTINGS),
                (30103, MenuGui.STATE_EXIT)
            ]
            if self.musicEnabled:
                items.insert(0, (30106, MenuGui.STATE_MUSIC_QUIZ))
            if self.tvShowsEnabled:
                items.insert(0, (30101, MenuGui.STATE_TV_QUIZ))
            if self.moviesEnabled:
                items.insert(0, (30100, MenuGui.STATE_MOVIE_QUIZ))
        elif self.state == MenuGui.STATE_ABOUT:
            items = [
                (30801, None),
                (30802, None),
                (M_GO_BACK, None),
            ]

        listControl.addItems(self._buildMenuItemsList(items))
        self.setFocus(listControl)

    @buggalo.buggalo_try_except()
    def onClick(self, controlId):
        """
        @param controlId: id of the control that was clicked
        @type controlId: int
        """
        if controlId == MenuGui.C_MENU_LIST:
            self.getControl(MenuGui.C_MENU_VISIBILITY).setVisible(True)
            xbmc.sleep(350)

            if self.state == MenuGui.STATE_MAIN:
                item = self.getControl(MenuGui.C_MENU_LIST).getSelectedItem()
                self.state = int(item.getProperty('state'))

                if self.state == MenuGui.STATE_MOVIE_QUIZ:
                    gameInstance = game.UnlimitedGame(game.GAMETYPE_MOVIE)
                    self.close()
                    self.quizGui.newGame(gameInstance)
                    return
                elif self.state == MenuGui.STATE_ABOUT:
                    f = open(os.path.join(ADDON.getAddonInfo('path'), 'about.txt'))
                    self.getControl(MenuGui.C_MENU_ABOUT_TEXT).setText(f.read())
                    f.close()
                    self.getControl(MenuGui.C_MENU_ABOUT_VISIBILITY).setVisible(False)
                elif self.state == MenuGui.STATE_DOWNLOAD_IMDB:
                    imdb.downloadData()
                    self.state = MenuGui.STATE_MAIN
                elif self.state == MenuGui.STATE_OPEN_SETTINGS:
                    ADDON.openSettings()
                    self.quizGui.onSettingsChanged()
                    self.state = MenuGui.STATE_MAIN
                elif self.state == MenuGui.STATE_EXIT:
                    self.quizGui.close()
                    self.close()
                    return
                self.updateMenu()

            elif self.state == MenuGui.STATE_ABOUT:
                self.getControl(MenuGui.C_MENU_ABOUT_VISIBILITY).setVisible(True)
                idx = self.getControl(MenuGui.C_MENU_LIST).getSelectedPosition()
                xbmc.sleep(250)

                if idx == 0:
                    f = open(os.path.join(ADDON.getAddonInfo('path'), 'about.txt'))
                    self.getControl(MenuGui.C_MENU_ABOUT_TEXT).setText(f.read())
                    f.close()
                    self.getControl(MenuGui.C_MENU_ABOUT_VISIBILITY).setVisible(False)
                elif idx == 1:
                    f = open(os.path.join(ADDON.getAddonInfo('changelog'))) #todo: this didn't work
                    self.getControl(MenuGui.C_MENU_ABOUT_TEXT).setText(f.read())
                    f.close()
                    self.getControl(MenuGui.C_MENU_ABOUT_VISIBILITY).setVisible(False)
                elif idx == 2:
                    self.getControl(MenuGui.C_MENU_ABOUT_VISIBILITY).setVisible(True)
                    self.state = MenuGui.STATE_MAIN
                    self.updateMenu()

            self.getControl(MenuGui.C_MENU_VISIBILITY).setVisible(False)

    @buggalo.buggalo_try_except()
    def onFocus(self, controlId):
        pass

class QuizGui(xbmcgui.WindowXML):
    C_MAIN_FIRST_ANSWER = 4000
    C_MAIN_LAST_ANSWER = 4003
    C_MAIN_REPLAY = 4010
    C_MAIN_EXIT = 4011
    C_MAIN_LOADING = 4020
    C_MAIN_COVER_IMAGE = 4200
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
    C_MAIN_PHOTO_VISIBILITY = 5001
    C_MAIN_QUOTE_VISIBILITY = 5004
    C_MAIN_THREE_PHOTOS_VISIBILITY = 5006
    C_MAIN_CORRECT_VISIBILITY = 5002
    C_MAIN_INCORRECT_VISIBILITY = 5003
    C_MAIN_LOADING_VISIBILITY = 5005
    C_MAIN_COVER_IMAGE_VISIBILITY = 5007

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
        self.onSettingsChanged()

    def onSettingsChanged(self):
        # minPercent = int(ADDON.getSetting('question.whatmovieisthis.min_percent'))
        minPercent = ADDON.getSettingInt('question.whatmovieisthis.min_percent')
        maxPercent = ADDON.getSettingInt('question.whatmovieisthis.max_percent')
        duration = ADDON.getSettingInt('question.whatmovieisthis.duration')
        logger.log(f"setting new player with min:{minPercent} max:{maxPercent}, duration:{duration}")
        if self.player is not None:
            self.player.stopPlayback(True)
            del self.player
        self.player = player.TimeLimitedPlayer(min(minPercent, maxPercent), max(minPercent, maxPercent), duration)

    @buggalo.buggalo_try_except()
    def onInit(self):
        self.getControl(2).setVisible(False)
        startTime = datetime.datetime.now()
        question.IMDB.loadData()
        delta = datetime.datetime.now() - startTime
        # if delta.seconds < 2:
        #     xbmc.sleep(1000 * (2 - delta.seconds))
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
            idx = MPAA_RATINGS.index(ADDON.getSetting('movie.rating.limit'))
            self.defaultLibraryFilters.extend(iter(library.buildRatingsFilters('mpaarating', MPAA_RATINGS[:idx])))

        elif gameInstance.getType() == game.GAMETYPE_TVSHOW and ADDON.getSetting(
                'tvshow.rating.limit.enabled') == 'true':
            idx = CONTENT_RATINGS.index(ADDON.getSetting('tvshow.rating.limit'))
            self.defaultLibraryFilters.extend(iter(library.buildRatingsFilters('rating', CONTENT_RATINGS[:idx])))

        if ADDON.getSetting(SETT_ONLY_WATCHED_MOVIES) == 'true':
            self.defaultLibraryFilters.extend(library.buildOnlyWathcedFilter())

        self.questionCandidates = question.getEnabledQuestionCandidates(self.gameInstance)

        self.question = None
        self.previousQuestions = []
        self.uiState = self.STATE_LOADING

        self.onNewQuestion()

    def close(self):
        if self.player:
            if self.player.isPlaying():
                self.player.stopPlayback(True)
        super().close()

    @buggalo.buggalo_try_except()
    def onAction(self, action):
        if self.uiState == self.STATE_SPLASH and (action.getId() == ACTION_PARENT_DIR or action.getId() == ACTION_PREVIOUS_MENU):
            self.close()
            return

        if action.getId() == ACTION_PARENT_DIR or action.getId() == ACTION_PREVIOUS_MENU:
            self.onGameOver()

        if self.uiState == self.STATE_LOADING:
            return
        elif action.getId() in [ACTION_REMOTE1]:
            self.setFocusId(self.C_MAIN_FIRST_ANSWER)
            self.onQuestionAnswered(self.question.getAnswer(0))
        elif action.getId() in [ACTION_REMOTE2, ACTION_JUMP_SMS2]:
            self.setFocusId(self.C_MAIN_FIRST_ANSWER + 1)
            self.onQuestionAnswered(self.question.getAnswer(1))
        elif action.getId() in [ACTION_REMOTE3, ACTION_JUMP_SMS3]:
            self.setFocusId(self.C_MAIN_FIRST_ANSWER + 2)
            self.onQuestionAnswered(self.question.getAnswer(2))
        elif action.getId() in [ACTION_REMOTE4, ACTION_JUMP_SMS4]:
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
        self.onThumbChanged(controlId)

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

        self.onThumbChanged()

        displayType = self.question.getDisplayType()
        if self.question.getFanartFile():
            self.getControl(self.C_MAIN_MOVIE_BACKGROUND).setImage(self.question.getFanartFile())
        elif isinstance(displayType, question.AudioDisplayType):
            self.getControl(self.C_MAIN_MOVIE_BACKGROUND).setImage(BACKGROUND_THEME)
        else:
            self.getControl(self.C_MAIN_MOVIE_BACKGROUND).setImage(self.defaultBackground)

        if isinstance(displayType, question.VideoDisplayType):
            self.getControl(self.C_MAIN_VIDEO_FILE_NOT_FOUND).setVisible(False)
            xbmc.sleep(1500)  # give skin animation time to execute
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

        if answer is not None and answer.correct:
            xbmc.playSFX(AUDIO_CORRECT)
            self.getControl(self.C_MAIN_CORRECT_VISIBILITY).setVisible(False)
        else:
            xbmc.playSFX(AUDIO_WRONG)
            self.getControl(self.C_MAIN_INCORRECT_VISIBILITY).setVisible(False)

        if self.player.isPlaying():
            self.player.stopPlayback()

        threading.Timer(0.5, self.onQuestionAnswerFeedbackTimer).start()
        if ADDON.getSetting('show.correct.answer') == 'true' and not answer.correct:
            for idx, answer in enumerate(self.question.getAnswers()):
                if answer.correct:
                    self.getControl(self.C_MAIN_FIRST_ANSWER + idx).setLabel('[B]%s[/B]' % answer.text)
                    self.setFocusId(self.C_MAIN_FIRST_ANSWER + idx)
                    self.onThumbChanged(self.C_MAIN_FIRST_ANSWER + idx)
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

    def onThumbChanged(self, controlId=None):
        if self.question is None:
            return  # not initialized yet

        if controlId is None:
            controlId = self.getFocusId()

        if self.C_MAIN_FIRST_ANSWER <= controlId <= self.C_MAIN_LAST_ANSWER:
            answer = self.question.getAnswer(controlId - self.C_MAIN_FIRST_ANSWER)
            coverImage = self.getControl(self.C_MAIN_COVER_IMAGE)
            if answer is not None and answer.coverFile is not None:
                self.getControl(self.C_MAIN_COVER_IMAGE_VISIBILITY).setVisible(False)
                coverImage.setImage(answer.coverFile)
            elif answer is not None and answer.coverFile is not None:
                self.getControl(self.C_MAIN_COVER_IMAGE_VISIBILITY).setVisible(False)
                coverImage.setImage(NO_PHOTO_IMAGE)
            else:
                self.getControl(self.C_MAIN_COVER_IMAGE_VISIBILITY).setVisible(True)

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
