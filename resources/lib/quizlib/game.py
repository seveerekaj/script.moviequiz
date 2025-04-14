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

from . import highscore
from .strings import *

GAMETYPE_MOVIE = "movie"
GAMETYPE_TVSHOW = "tvshow"
GAMETYPE_MUSIC = "music"

class UnlimitedGame():
    def __init__(self, type):
        self.type = type

    def __repr__(self):
        return "<UnlimitedGame>"

    def __eq__(self, other):
        return type(other) == UnlimitedGame and self.type == other.type

    def getType(self):
        return self.type
        
    def isGameFinished(self):
        return False
        
    def questionAnswered(self, correct):
        pass
        
    def addHighscore(self):
        return None
        
class CompetitiveGame():
    def __init__(self, type, nbQuestions, name):
        self.type = type
        self.nbQuestions = nbQuestions
        self.name = name
        self.curQuestion = 0
        self.nbCorrectAnswers = 0

    def __repr__(self):
        return "<CompetitiveGame>"

    def __eq__(self, other):
        return type(other) == CompetitiveGame and self.type == other.type

    def getType(self):
        return self.type
        
    def isGameFinished(self):
        return self.curQuestion >= self.nbQuestions
        
    def questionAnswered(self, correct):
        self.curQuestion = self.curQuestion + 1
        if correct:
            self.nbCorrectAnswers = self.nbCorrectAnswers + 1
            
    def addHighscore(self):
        if self.nbCorrectAnswers > 0 and self.curQuestion >= self.nbQuestions:
            hs = highscore.Highscore()
            hs.add(self.name, self.nbQuestions, self.nbCorrectAnswers, self.type)
            report = strings(M_SCORE_REPORT).format(self.nbCorrectAnswers, self.nbQuestions)
            self.nbCorrectAnswers = 0
            return report
        else:
            return None
