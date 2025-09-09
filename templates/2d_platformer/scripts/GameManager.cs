using UnityEngine;

public class GameManager : MonoBehaviour {
    void Start() { DontDestroyOnLoad(this.gameObject); }
}

