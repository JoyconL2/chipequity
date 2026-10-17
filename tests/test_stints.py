"""Turning possessions into stints: points add up, lineup changes split stints, time is continuous."""
import pytest
pytest.importorskip("pbpstats")
import build_stints as B

H, A = 1, 2


class Ev:
    def __init__(self, t, hp, ap, team=None, pts=0, period=1):
        self.seconds_remaining, self.period, self.team_id = t, period, team
        self.current_players = {H: hp, A: ap}
        self.is_made = pts > 0; self.shot_value = pts


class FieldGoal(Ev): pass        # build_stints recognises shots by class name


class Poss:
    def __init__(self, off, events): self.offense_team_id, self.events = off, events


def test_stints_from_possessions():
    h1, h2, a1 = [1, 2, 3, 4, 5], [1, 2, 3, 4, 6], [11, 12, 13, 14, 15]
    poss = [Poss(H, [FieldGoal(700, h1, a1, H, 2)]),
            Poss(A, [FieldGoal(680, h1, a1, A, 3)]),
            Poss(H, [FieldGoal(600, h2, a1, H, 3)]),          # sub: new home lineup
            Poss(A, [FieldGoal(500, h2, a1, A, 0)])]
    rows, hs, as_, skipped = B.game_stints(poss, "001", "2020-21", "rs", "", H, A)
    assert (hs, as_) == (5, 3) and skipped == 0
    assert len(rows) == 2
    assert rows[0]["start_sec"] == 720 and rows[0]["end_sec"] == rows[1]["start_sec"] == 600 and rows[1]["end_sec"] == 0
    assert rows[0]["home_pts"] == 2 and rows[0]["away_pts"] == 3 and rows[0]["home_poss"] == 1 and rows[0]["away_poss"] == 1
    assert rows[1]["home_players"] == "1-2-3-4-6" and rows[1]["start_margin"] == -1
