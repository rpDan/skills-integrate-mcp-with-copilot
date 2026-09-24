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

    def student_headers(self, email):
        return {"X-Student-Email": email}

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
            headers=self.student_headers("captain@mergington.edu"),
        )
        self.assertEqual(too_small.status_code, 400)

        created = self.client.post(
            "/activities/Soccer%20Team/teams",
            json={
                "team_name": "Falcons",
                "leader_email": "captain@mergington.edu",
                "members": ["mate@mergington.edu"],
            },
            headers=self.student_headers("captain@mergington.edu"),
        )
        self.assertEqual(created.status_code, 200)

        joined = self.client.post(
            "/activities/Soccer%20Team/teams/Falcons/join",
            json={"email": "new@mergington.edu"},
            headers=self.student_headers("new@mergington.edu"),
        )
        self.assertEqual(joined.status_code, 200)

        duplicate = self.client.post(
            "/activities/Soccer%20Team/teams/Falcons/join",
            json={"email": "new@mergington.edu"},
            headers=self.student_headers("new@mergington.edu"),
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
            headers=self.student_headers("leader@mergington.edu"),
        )
        self.assertEqual(created.status_code, 200)

        grouped = self.client.get("/activities/Soccer%20Team/participants", headers=headers)
        self.assertEqual(grouped.status_code, 200)
        self.assertEqual(grouped.json()["enrollment_type"], "team")
        self.assertTrue(any(team["team_name"] == "Wolves" for team in grouped.json()["teams"]))

        enrollment = self.client.get(
            "/activities/Soccer%20Team/enrollment?email=leader@mergington.edu",
            headers=self.student_headers("leader@mergington.edu"),
        )
        self.assertEqual(enrollment.status_code, 200)
        self.assertTrue(enrollment.json()["enrolled"])

        left = self.client.delete(
            "/activities/Soccer%20Team/enrollment?email=member@mergington.edu",
            headers=self.student_headers("member@mergington.edu"),
        )
        self.assertEqual(left.status_code, 200)

        blocked = self.client.delete(
            "/activities/Debate%20Team/enrollment?email=henry@mergington.edu",
            headers=self.student_headers("henry@mergington.edu"),
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["detail"], "Students cannot leave this activity")

    def test_non_leader_cannot_add_team_member(self):
        teacher_headers = self.login_headers()
        created = self.client.post(
            "/activities/Soccer%20Team/teams",
            json={
                "team_name": "Owls",
                "leader_email": "leader2@mergington.edu",
                "members": ["member2@mergington.edu"],
            },
            headers=self.student_headers("leader2@mergington.edu"),
        )
        self.assertEqual(created.status_code, 200)

        not_leader = self.client.post(
            "/activities/Soccer%20Team/teams/Owls/members",
            json={"leader_email": "intruder@mergington.edu", "email": "extra2@mergington.edu"},
            headers=teacher_headers,
        )
        self.assertEqual(not_leader.status_code, 403)

    def test_configuration_rejects_mode_change_with_active_participants(self):
        headers = self.login_headers()
        response = self.client.patch(
            "/activities/Chess%20Club/configuration",
            json={"enrollment_type": "team"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Cannot change enrollment type with active participants",
        )

    def test_configuration_switches_empty_activity_to_team(self):
        headers = self.login_headers()

        clear_one = self.client.delete(
            "/activities/Math%20Club/unregister?email=james@mergington.edu",
            headers=headers,
        )
        clear_two = self.client.delete(
            "/activities/Math%20Club/unregister?email=benjamin@mergington.edu",
            headers=headers,
        )
        self.assertEqual(clear_one.status_code, 200)
        self.assertEqual(clear_two.status_code, 200)

        switched = self.client.patch(
            "/activities/Math%20Club/configuration",
            json={"enrollment_type": "team", "min_team_size": 2, "max_team_size": 3},
            headers=headers,
        )
        self.assertEqual(switched.status_code, 200)
        self.assertEqual(switched.json()["enrollment_type"], "team")
        self.assertEqual(switched.json()["min_team_size"], 2)
        self.assertEqual(switched.json()["max_team_size"], 3)

    def test_configuration_rejects_invalid_team_size_range(self):
        headers = self.login_headers()
        response = self.client.patch(
            "/activities/Soccer%20Team/configuration",
            json={"min_team_size": 6, "max_team_size": 5},
            headers=headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "min_team_size cannot exceed max_team_size")

    def test_configuration_invalid_switch_does_not_mutate_activity(self):
        headers = self.login_headers()
        self.client.delete(
            "/activities/Math%20Club/unregister?email=james@mergington.edu",
            headers=headers,
        )
        self.client.delete(
            "/activities/Math%20Club/unregister?email=benjamin@mergington.edu",
            headers=headers,
        )

        invalid = self.client.patch(
            "/activities/Math%20Club/configuration",
            json={"enrollment_type": "team", "min_team_size": 4, "max_team_size": 3},
            headers=headers,
        )
        self.assertEqual(invalid.status_code, 400)

        activities = self.client.get("/activities").json()
        self.assertEqual(activities["Math Club"]["enrollment_type"], "individual")

    def test_configuration_rejects_team_size_for_individual_mode(self):
        headers = self.login_headers()
        response = self.client.patch(
            "/activities/Chess%20Club/configuration",
            json={"min_team_size": 2},
            headers=headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Team size settings require team enrollment",
        )

    def test_allow_student_leave_configuration_controls_self_service_leave(self):
        headers = self.login_headers()

        updated = self.client.patch(
            "/activities/Chess%20Club/configuration",
            json={"allow_student_leave": False},
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.json()["allow_student_leave"])

        student_leave = self.client.delete(
            "/activities/Chess%20Club/enrollment?email=michael@mergington.edu",
            headers=self.student_headers("michael@mergington.edu"),
        )
        self.assertEqual(student_leave.status_code, 403)

        teacher_leave = self.client.delete(
            "/activities/Chess%20Club/enrollment?email=michael@mergington.edu",
            headers=headers,
        )
        self.assertEqual(teacher_leave.status_code, 200)


if __name__ == "__main__":
    unittest.main()
