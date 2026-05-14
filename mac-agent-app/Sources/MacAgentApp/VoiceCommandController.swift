import AVFoundation
import Foundation
import Speech

enum VoiceCommandError: LocalizedError {
    case speechPermissionDenied
    case microphonePermissionDenied
    case microphonePermissionNotDetermined
    case recognizerUnavailable
    case microphoneUnavailable
    case alreadyListening
    case noSpeech

    var errorDescription: String? {
        switch self {
        case .speechPermissionDenied:
            return "Speech recognition permission is required."
        case .microphonePermissionDenied:
            return "Microphone permission is required."
        case .microphonePermissionNotDetermined:
            return "Microphone permission is not granted yet. Open System Settings > Privacy & Security > Microphone and enable Mac Agent."
        case .recognizerUnavailable:
            return "Speech recognizer is unavailable."
        case .microphoneUnavailable:
            return "Microphone input is unavailable."
        case .alreadyListening:
            return "Already listening."
        case .noSpeech:
            return "No speech was recognized."
        }
    }
}

@MainActor
final class VoiceCommandController {
    private let config: AppConfig
    private var recognizer: SFSpeechRecognizer?
    private var audioEngine: AVAudioEngine?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var latestTranscript = ""
    private var isListening = false
    private var tapInstalled = false

    init(config: AppConfig) {
        self.config = config
        AppLog.write("VoiceCommandController initialized")
    }

    func listenOnce(
        onPartial: @escaping @MainActor (String) -> Void,
        completion: @escaping @MainActor (Result<String, Error>) -> Void
    ) {
        AppLog.write("listenOnce entered")
        guard !isListening else {
            AppLog.write("listenOnce rejected: already listening")
            completion(.failure(VoiceCommandError.alreadyListening))
            return
        }

        requestPermissions { [weak self] result in
            switch result {
            case .success:
                self?.startRecognition(onPartial: onPartial, completion: completion)
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }

    private func requestPermissions(completion: @escaping @MainActor (Result<Void, Error>) -> Void) {
        AppLog.write("requestPermissions entered")
        AppLog.write("checking speech authorization status")
        let speechStatus = SFSpeechRecognizer.authorizationStatus()
        AppLog.write("current speech authorization status: \(speechStatus.rawValue)")
        if speechStatus == .denied || speechStatus == .restricted {
            AppLog.write("speech permission denied/restricted")
            completion(.failure(VoiceCommandError.speechPermissionDenied))
            return
        }

        AppLog.write("checking microphone authorization status")
        let micStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        AppLog.write("current microphone authorization status: \(micStatus.rawValue)")
        if micStatus == .notDetermined {
            AppLog.write("microphone permission not determined; avoiding requestAccess crash path")
            completion(.failure(VoiceCommandError.microphonePermissionNotDetermined))
            return
        }
        if micStatus == .denied || micStatus == .restricted {
            AppLog.write("microphone permission denied/restricted")
            completion(.failure(VoiceCommandError.microphonePermissionDenied))
            return
        }

        SFSpeechRecognizer.requestAuthorization { speechStatus in
            Task { @MainActor in
                AppLog.write("speech authorization status: \(speechStatus.rawValue)")
                guard speechStatus == .authorized else {
                    completion(.failure(VoiceCommandError.speechPermissionDenied))
                    return
                }

                completion(.success(()))
            }
        }
    }

    private func startRecognition(
        onPartial: @escaping @MainActor (String) -> Void,
        completion: @escaping @MainActor (Result<String, Error>) -> Void
    ) {
        AppLog.write("startRecognition entered")
        if recognizer == nil {
            AppLog.write("creating SFSpeechRecognizer")
            recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
            AppLog.write("created SFSpeechRecognizer isNil=\(recognizer == nil)")
        }
        guard let recognizer, recognizer.isAvailable else {
            AppLog.write("recognizer unavailable")
            completion(.failure(VoiceCommandError.recognizerUnavailable))
            return
        }

        if audioEngine == nil {
            AppLog.write("creating AVAudioEngine")
            audioEngine = AVAudioEngine()
            AppLog.write("created AVAudioEngine")
        }
        guard let audioEngine else {
            AppLog.write("audio engine unavailable")
            completion(.failure(VoiceCommandError.microphoneUnavailable))
            return
        }

        stopRecognition()
        isListening = true
        latestTranscript = ""

        let recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        AppLog.write("created recognition request")
        recognitionRequest.shouldReportPartialResults = true
        request = recognitionRequest

        let input = audioEngine.inputNode
        AppLog.write("got audio input node")
        let format = input.outputFormat(forBus: 0)
        AppLog.write("input format sampleRate=\(format.sampleRate) channels=\(format.channelCount)")
        guard format.sampleRate > 0, format.channelCount > 0 else {
            stopRecognition()
            completion(.failure(VoiceCommandError.microphoneUnavailable))
            return
        }

        AppLog.write("installing audio tap")
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
            recognitionRequest.append(buffer)
        }
        tapInstalled = true
        AppLog.write("installed audio tap")

        AppLog.write("creating recognition task")
        task = recognizer.recognitionTask(with: recognitionRequest) { [weak self] result, error in
            Task { @MainActor in
                guard self?.isListening == true else { return }
                if let result {
                    let transcript = result.bestTranscription.formattedString
                    self?.latestTranscript = transcript
                    onPartial(transcript)
                }
                if error != nil {
                    self?.finishRecognition(completion: completion)
                }
            }
        }
        AppLog.write("created recognition task")

        do {
            AppLog.write("preparing audio engine")
            audioEngine.prepare()
            AppLog.write("starting audio engine")
            try audioEngine.start()
            AppLog.write("audio engine started")
        } catch {
            stopRecognition()
            AppLog.write("audio engine failed: \(error.localizedDescription)")
            completion(.failure(error))
            return
        }

        Task { @MainActor [weak self] in
            try? await Task.sleep(for: .seconds(4))
            guard self?.isListening == true else { return }
            self?.finishRecognition(completion: completion)
        }
    }

    private func finishRecognition(completion: @escaping @MainActor (Result<String, Error>) -> Void) {
        guard isListening else { return }
        let transcript = latestTranscript.trimmingCharacters(in: .whitespacesAndNewlines)
        AppLog.write("finishRecognition transcriptLength=\(transcript.count)")
        stopRecognition()

        if transcript.isEmpty {
            completion(.failure(VoiceCommandError.noSpeech))
        } else {
            completion(.success(transcript))
        }
    }

    private func stopRecognition() {
        guard let audioEngine else {
            isListening = false
            return
        }
        if audioEngine.isRunning {
            audioEngine.stop()
        }
        if tapInstalled {
            audioEngine.inputNode.removeTap(onBus: 0)
            tapInstalled = false
        }
        request?.endAudio()
        task?.cancel()
        request = nil
        task = nil
        isListening = false
    }
}
