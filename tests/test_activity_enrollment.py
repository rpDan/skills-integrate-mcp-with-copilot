import copy
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
import app as app_module  # noqa: E402


class ActivityEnrollmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app_module.app)
        cls.original_activities = copy.deepcopy(app_module.activities)

    def setUp(self):
        app_module.activities = copy.deepcopy(self.original_activities)
        app_module.active_tokens.clear()

    def login_headers(self):
        response = self.client.post(
            "/auth/login",
            json={"username": "teacher", "password": "mergington-teacher"},
        )
        self.assertEqual(response.status_code, 200)
        token = response.json()["access_token"]
        return {"Authorization": "Bearer " + token}

    def test_individual_signup_prevents_duplicate_and_capacity(self):
        headers = self.login_headers()

        duplicate = self.client.post(
            "/activities/Chess%20Club/signup?email=michael@mergington.edu",
            headers=headers,
        )
        self.assertEqual(duplicate.status_code, 400)

        for idx in range(10):
            enroll = self.client.post(
                f"/activities/Chess%20Club/signup?email=student{idx}@mergington.edu",
                headers=headers,
            )
            self.assertEqual(enroll.status_code, 200)

        over_capacity = self.client.post(
            "/activities/Chess%20Club/signup?email=extra@mergington.edu",
            headers=headers,
        )
        self.assertEqual(over_capacity.status_code, 400)
        self.assertEqual(over_capacity.json()["detail"], "Activity is at capacity")

    def test_team_creation_validates_membership_and_allows_join(self):
        too_small = self.client.post(
            "/activities/Soccer%20Team/teams",
            json={"team_name": "Falcons", "leader_email": "captain@mergington.edu", "members": []},
        )
        self.assertEqual(too_small.status_code, 400)

        created = self.client.post(
            "/activities/Soccer%20Team/teams",
            json={
                "team_name": "Falcons",
                "leader_email": "captain@mergington.edu",
                "members": ["mate@mergington.edu"],
            },
        )
        self.assertEqual(created.status_code, 200)

        joined = self.client.post(
            "/activities/Soccer%20Team/teams/Falcons/join",
            json={"email": "new@mergington.edu"},
        )
        self.assertEqual(joined.status_code, 200)

        duplicate = self.client.post(
            "/activities/Soccer%20Team/teams/Falcons/join",
            json={"email": "new@mergington.edu"},
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["detail"], "Student is already signed up")

    def test_grouped_participants_and_leave_policy(self):
        headers = self.login_headers()

        created = self.client.post(
            "/activities/Soccer%20Team/teams",
            json={
                "team_name": "Wolves",
                "leader_email": "leader@mergington.edu",
                "members": ["member@mergington.edu"],
            },
        )
        self.assertEqual(created.status_code, 200)

        grouped = self.client.get("/activities/Soccer%20Team/participants", headers=headers)
        self.assertEqual(grouped.status_code, 200)
        self.assertEqual(grouped.json()["enrollment_type"], "team")
        self.assertTrue(any(team["team_name"] == "Wolves" for team in grouped.json()["teams"]))

        enrollment = self.client.get(
            "/activities/Soccer%20Team/enrollment?email=leader@mergington.edu"
        )
        self.assertEqual(enrollment.status_code, 200)
        self.assertTrue(enrollment.json()["enrolled"])

        left = self.client.delete("/activities/Soccer%20Team/enrollment?email=member@mergington.edu")
        self.assertEqual(left.status_code, 200)

        blocked = self.client.delete("/activities/Debate%20Team/enrollment?email=henry@mergington.edu")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["detail"], "Students cannot leave this activity")


if __name__ == "__main__":
    unittest.main()
