# NIGHTMARE ENGINE — Unity VR FNAF Setup Guide

## Requirements
- Unity 2022 LTS or later
- XR Interaction Toolkit 2.5+
- NativeWebSocket package (see below)
- Newtonsoft.Json (included in Unity 2021+)
- A VR headset (Meta Quest 2/3 recommended) or PC VR via Link

---

## 1. Unity Project Setup

1. Create a new Unity 3D (URP) project
2. Install **XR Interaction Toolkit** via Package Manager
3. Install **NativeWebSocket** via Package Manager:
   - Window → Package Manager → + → Add package from git URL
   - `https://github.com/endel/NativeWebSocket.git#upm`
4. Copy the `Scripts/` folder into your project's `Assets/Scripts/`

---

## 2. Scene Hierarchy

```
FnafNight [Scene]
├── NetworkManager          (FnafWebSocketClient.cs)
├── NightGameManager        (NightGameManager.cs)
├── XR Rig
│   ├── Camera Offset
│   │   └── Main Camera     (OfficeVRRig.cs)
│   └── LocomotionSystem
├── Office
│   ├── OfficeAnchor        (empty, centre of player area)
│   ├── Desk
│   ├── LeftDoor            (DoorLightController.cs — side="left")
│   │   ├── DoorMesh        (Animator with DoorClosed bool param)
│   │   ├── DoorButton      (XRSimpleInteractable → ToggleDoor())
│   │   ├── LightButton     (XRSimpleInteractable → ToggleLight())
│   │   ├── HallwayCamera   (Camera → RenderTexture RT_LeftHall)
│   │   └── HallwaySpotLight
│   ├── RightDoor           (DoorLightController.cs — side="right")
│   │   └── [same as LeftDoor]
│   ├── CameraTablet        (CameraMonitor.cs + XRGrabInteractable)
│   │   └── TabletCanvas    (World Space)
│   │       ├── FeedDisplay (RawImage)
│   │       ├── CameraLabel (TextMeshPro)
│   │       └── CamButtons  (cam1A…cam5 buttons → SwitchTo("camXX"))
│   ├── HUD Canvas          (Screen Space - Overlay)
│   │   ├── PowerBar        (PowerManager.cs)
│   │   ├── HourLabel       (TextMeshPro)
│   │   └── PhaseLabel
│   └── OfficeLights[]      (Point/Spot lights)
│
├── RoomAnchors             (Parent for all room anchor empties)
│   ├── show_stage
│   ├── dining_area
│   ├── backstage
│   ├── supply_closet
│   ├── west_hall
│   ├── west_hall_corner
│   ├── pirate_cove
│   ├── restrooms
│   ├── kitchen
│   ├── east_hall
│   └── east_hall_corner
│
├── AnimatronicPrefabs
│   ├── Freddy              (AnimatronicAvatarController.cs — disabled by default)
│   ├── Bonnie
│   ├── Chica
│   └── Foxy
│
└── JumpscareController     (JumpscareController.cs)
    └── ScreenFade          (Full-screen black Image, Screen Space Overlay)
```

---

## 3. Backend Connection

1. Start the Python server:
   ```bash
   cd /path/to/Nightmare-Engine-
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --reload
   ```

2. Create a Nightmare Engine session:
   ```bash
   curl -X POST http://localhost:8000/api/v1/experience/create \
     -H "Content-Type: application/json" \
     -d '{"user_id":"player1","experience_type":"solo"}'
   ```
   Note the `experience_id` from the response.

3. In Unity, set these on **NightGameManager**:
   - `BackendUrl`: `http://<your-PC-IP>:8000`
   - `ExpId`: the `experience_id` from step 2
   - `NightNumber`: 1 (or 1-7)

4. Press Play, then call `NightGameManager.StartNight()` (wire to a UI button).

---

## 4. Animatronic Animator Setup

Each animatronic prefab needs an **Animator Controller** with:

| Parameter   | Type    | Description                    |
|-------------|---------|--------------------------------|
| `Idle`      | Bool    | Standard idle loop             |
| `AtDoor`    | Bool    | Standing at door animation     |
| `Charge`    | Trigger | Foxy sprint animation          |
| `Jumpscare` | Trigger | Full jumpscare animation       |

---

## 5. Camera RenderTextures

For each camera room, create a RenderTexture (512×512) and assign it to:
- The Camera component in that room
- The CameraMonitor's CameraFeeds array (matching cam ID)

Camera IDs:
| cam1A | Show Stage       |
| cam1B | Dining Area      |
| cam1C | Pirate Cove      |
| cam2A | West Hall        |
| cam2B | West Hall Corner |
| cam3  | East Hall        |
| cam4A | East Hall Corner |
| cam4B | Restrooms        |
| cam5  | Backstage        |

---

## 6. Night Numbers & Difficulty

| Night | Freddy | Bonnie | Chica | Foxy |
|-------|--------|--------|-------|------|
| 1     | 0      | 0      | 0     | 0    |
| 2     | 0      | 3      | 1     | 2    |
| 3     | 1      | 1      | 2     | 6    |
| 4     | 1      | 2      | 4     | 10   |
| 5     | 3      | 5      | 7     | 16   |
| 6     | 4      | 10     | 12    | 16   |
| 7     | 20     | 20     | 20    | 20   |

AI levels can be changed at runtime:
```bash
curl -X POST http://localhost:8000/api/v1/fnaf/<exp_id>/ai_levels \
  -H "Content-Type: application/json" \
  -d '{"freddy":5,"bonnie":5,"chica":5,"foxy":5}'
```

---

## 7. Biometric Adaptive Difficulty

The Nightmare Engine's biometric pipeline runs in parallel.
If the player's detected fear level rises (via webcam HR / emotion), animatronic
AI levels are automatically increased by up to +4 points on top of the base night level.

Install optional deps for this:
```bash
pip install opencv-python mediapipe deepface tensorflow
```
