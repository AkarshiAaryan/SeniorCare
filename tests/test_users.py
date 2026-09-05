def test_create_and_get_caregiver(client):
    res = client.post("/caregivers", json={"name": "Sarah Nurse", "contact": "+1-555-0199"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Sarah Nurse"
    assert data["contact"] == "+1-555-0199"
    assert "id" in data

    caregiver_id = data["id"]
    get_res = client.get(f"/caregivers/{caregiver_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Sarah Nurse"


def test_get_nonexistent_caregiver(client):
    res = client.get("/caregivers/999")
    assert res.status_code == 404
    assert res.json()["detail"] == "Caregiver not found"


def test_create_user_with_caregiver(client):
    # 1. Create caregiver
    cg_res = client.post("/caregivers", json={"name": "Doctor Green", "contact": "+1-555-1234"})
    cg_id = cg_res.json()["id"]

    # 2. Create user assigned to caregiver
    user_res = client.post("/users", json={
        "name": "Arthur Dent",
        "age": 79,
        "preferred_language": "English",
        "caregiver_id": cg_id
    })
    assert user_res.status_code == 201
    user_data = user_res.json()
    assert user_data["name"] == "Arthur Dent"
    assert user_data["age"] == 79
    assert user_data["caregiver_id"] == cg_id


def test_create_user_invalid_caregiver_fails(client):
    user_res = client.post("/users", json={
        "name": "Arthur Dent",
        "age": 79,
        "preferred_language": "English",
        "caregiver_id": 9999
    })
    assert user_res.status_code == 400
    assert "Specified Caregiver ID does not exist" in user_res.json()["detail"]


def test_get_and_update_user(client):
    user_res = client.post("/users", json={"name": "Martha Wayne", "age": 75})
    assert user_res.status_code == 201
    user_id = user_res.json()["id"]

    # Update age and language
    update_res = client.put(f"/users/{user_id}", json={
        "age": 76,
        "preferred_language": "Spanish"
    })
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["age"] == 76
    assert updated["preferred_language"] == "Spanish"
    assert updated["name"] == "Martha Wayne"


def test_update_nonexistent_user(client):
    update_res = client.put("/users/9999", json={"age": 80})
    assert update_res.status_code == 404
