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

from quizlib.strings import *

GAMETYPE_MOVIE = "movie"
GAMETYPE_TVSHOW = "tvshow"
GAMETYPE_MUSIC = "music"


class Game:
    def __init__(self, type, interactive):
        self.type = type
        self.interactive = interactive
        self.points = 0
        self.correctAnswers = 0
        self.wrongAnswers = 0

    def correctAnswer(self, points):
        self.correctAnswers += 1
        self.points += points

    def wrongAnswer(self):
        self.wrongAnswers += 1

    def isGameOver(self):
        raise

    def getStatsString(self):
        return ''

    def getType(self):
        return self.type

    def setType(self, type):
        self.type = type

    def getPoints(self):
        return self.points

    def getTotalAnswers(self):
        return self.correctAnswers + self.wrongAnswers

    def getCorrectAnswers(self):
        return self.correctAnswers

    def getWrongAnswers(self):
        return self.wrongAnswers

    def getGameType(self):
        raise

    def getGameSubType(self):
        return -1

    def isInteractive(self):
        return self.interactive

    def reset(self):
        self.points = 0
        self.correctAnswers = 0
        self.wrongAnswers = 0


class UnlimitedGame(Game):
    def __init__(self, type, interactive):
        super().__init__(type, interactive)

    def isGameOver(self):
        return False

    def getGameType(self):
        return 'unlimited'

    def __repr__(self):
        return "<UnlimitedGame>"

    def __eq__(self, other):
        return type(other) == UnlimitedGame and self.type == other.type