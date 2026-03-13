/*
 * NIGHTMARE ENGINE — JumpscareController.cs
 *
 * Handles the game-over jumpscare sequence in VR.
 *
 * Sequence:
 *  1. Freeze all player input
 *  2. Fade to black (0.3 s)
 *  3. Snap the correct animatronic face to camera-space
 *  4. Play jumpscare animation + scream audio
 *  5. Screen flash
 *  6. Hold 2 s
 *  7. Fade back in → load Game Over screen (or restart)
 *
 * Setup:
 *  1. Attach to a persistent GameObject
 *  2. Assign ScreenFade (full-screen black Image on a Screen-Space overlay Canvas)
 *  3. Assign per-animatronic face prefabs (JumpscareEntry array)
 *  4. Assign ScreamClips per animatronic
 *  5. Assign MainCamera (your XR camera)
 */

using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.SceneManagement;
using TMPro;

public class JumpscareController : MonoBehaviour
{
    [Header("Screen")]
    public Image ScreenFade;                // full-screen black overlay
    public float FadeDuration = 0.3f;

    [Header("Camera")]
    public Transform MainCamera;

    [Header("Animatronic face prefabs")]
    public JumpscareEntry[] Jumpscares;

    [Header("Game Over UI")]
    public GameObject GameOverPanel;
    public TextMeshProUGUI CauseLabel;
    public string RestartSceneName = "";   // leave empty to just show panel

    // ── Private ───────────────────────────────────────────────────────────────

    private Dictionary<string, JumpscareEntry> _map = new();
    private AudioSource _audio;
    private bool _triggered = false;

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    private void Awake()
    {
        _audio = GetComponent<AudioSource>();
        if (_audio == null) _audio = gameObject.AddComponent<AudioSource>();

        foreach (var e in Jumpscares)
            _map[e.AnimatronicName] = e;

        if (ScreenFade != null)
        {
            var c = ScreenFade.color;
            c.a = 0f;
            ScreenFade.color = c;
            ScreenFade.gameObject.SetActive(false);
        }

        if (GameOverPanel != null) GameOverPanel.SetActive(false);
    }

    // ── Public API ────────────────────────────────────────────────────────────

    public void TriggerJumpscare(string animatronicName, string cause)
    {
        if (_triggered) return;
        _triggered = true;
        StartCoroutine(JumpscareSequence(animatronicName, cause));
    }

    // ── Sequence ──────────────────────────────────────────────────────────────

    private IEnumerator JumpscareSequence(string name, string cause)
    {
        // 1. Freeze input (disable XR rig locomotion)
        var locomotion = FindObjectOfType<UnityEngine.XR.Interaction.Toolkit.LocomotionSystem>();
        if (locomotion != null) locomotion.enabled = false;

        // 2. Fade to black
        yield return StartCoroutine(Fade(0f, 1f, FadeDuration));

        // 3. Spawn face at camera
        GameObject face = null;
        if (_map.TryGetValue(name, out JumpscareEntry entry))
        {
            if (entry.FacePrefab != null && MainCamera != null)
            {
                face = Instantiate(
                    entry.FacePrefab,
                    MainCamera.position + MainCamera.forward * 0.5f,
                    MainCamera.rotation
                );
            }

            // 4. Play scream
            if (entry.ScreamClip != null)
            {
                _audio.clip = entry.ScreamClip;
                _audio.Play();
            }
        }

        // 5. Fade in to reveal face
        yield return StartCoroutine(Fade(1f, 0f, FadeDuration));

        // 6. Play jumpscare animation on the avatar
        if (face != null)
        {
            Animator anim = face.GetComponent<Animator>();
            anim?.SetTrigger("Jumpscare");
        }

        // Flash
        yield return StartCoroutine(Flash());

        // 7. Hold
        yield return new WaitForSeconds(2f);

        // 8. Game over panel / restart
        if (face != null) Destroy(face);

        if (GameOverPanel != null)
        {
            GameOverPanel.SetActive(true);
            if (CauseLabel != null)
                CauseLabel.text = CauseFriendly(name, cause);
        }
        else if (!string.IsNullOrEmpty(RestartSceneName))
        {
            SceneManager.LoadScene(RestartSceneName);
        }
    }

    private IEnumerator Fade(float from, float to, float duration)
    {
        if (ScreenFade == null) yield break;
        ScreenFade.gameObject.SetActive(true);
        float elapsed = 0f;
        while (elapsed < duration)
        {
            elapsed += Time.deltaTime;
            float t = Mathf.Clamp01(elapsed / duration);
            var c = ScreenFade.color;
            c.a = Mathf.Lerp(from, to, t);
            ScreenFade.color = c;
            yield return null;
        }
        var final = ScreenFade.color;
        final.a = to;
        ScreenFade.color = final;
        if (to <= 0f) ScreenFade.gameObject.SetActive(false);
    }

    private IEnumerator Flash()
    {
        if (ScreenFade == null) yield break;
        ScreenFade.gameObject.SetActive(true);
        var c = ScreenFade.color;
        c.a = 0.8f;
        ScreenFade.color = c;
        yield return new WaitForSeconds(0.05f);
        c.a = 0f;
        ScreenFade.color = c;
        ScreenFade.gameObject.SetActive(false);
    }

    private static string CauseFriendly(string name, string cause)
    {
        string n = System.Globalization.CultureInfo.CurrentCulture.TextInfo
                        .ToTitleCase(name);
        return cause switch
        {
            "door_open"   => $"{n} got through the door.",
            "power_out"   => $"The power died. {n} found you in the dark.",
            "foxy_charge" => $"Foxy sprinted from Pirate Cove.",
            _             => $"You were caught by {n}.",
        };
    }
}

// ── Inspector-friendly entry ──────────────────────────────────────────────────

[System.Serializable]
public class JumpscareEntry
{
    public string     AnimatronicName;
    public GameObject FacePrefab;      // close-up face prefab for jumpscare
    public AudioClip  ScreamClip;
}
