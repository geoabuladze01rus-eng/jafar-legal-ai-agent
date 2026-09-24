import SwiftUI
import UniformTypeIdentifiers

struct JusticiaLiveTranscriptionView: View {
    @ObservedObject var voice: VoiceSessionViewModel
    @ObservedObject var workspace: JusticiaWorkspaceStore

    @State private var showingImporter = false
    @State private var importedAudioName: String?
    @State private var savedMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(
                title: "Транскрибация аудио",
                subtitle: "Локальная расшифровка с возможностью сохранить текст прямо в материалы выбранного дела."
            )

            HStack(alignment: .top, spacing: 14) {
                VStack(spacing: 14) {
                    controlCard
                    transcriptCard
                }
                .frame(maxWidth: .infinity)

                sidePanel
                    .frame(width: 330)
            }
        }
        .fileImporter(
            isPresented: $showingImporter,
            allowedContentTypes: [.audio],
            allowsMultipleSelection: false
        ) { result in
            guard case .success(let urls) = result, let url = urls.first else { return }
            importedAudioName = url.lastPathComponent
            savedMessage = nil
            Task {
                await voice.transcribeAudioFile(url)
            }
        }
    }

    private var controlCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top, spacing: 12) {
                JusticiaIconTile(systemName: "waveform", color: JusticiaTheme.blue)

                VStack(alignment: .leading, spacing: 4) {
                    Text(importedAudioName ?? (voice.isListening ? "Идёт запись с микрофона" : "Источник аудио не выбран"))
                        .font(.headline)
                    Text(statusText)
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }

                Spacer()

                Button {
                    showingImporter = true
                } label: {
                    Label("Аудиофайл", systemImage: "square.and.arrow.down")
                }
                .buttonStyle(.bordered)
                .disabled(voice.isListening || voice.isTranscribingFile)

                Button {
                    savedMessage = nil
                    if voice.isListening {
                        voice.stopTranscriptionOnly()
                    } else {
                        importedAudioName = nil
                        Task { await voice.start() }
                    }
                } label: {
                    Label(
                        voice.isListening ? "Остановить" : "Запись",
                        systemImage: voice.isListening ? "stop.circle.fill" : "record.circle"
                    )
                }
                .buttonStyle(.borderedProminent)
                .disabled(voice.isTranscribingFile)
            }

            if voice.isTranscribingFile {
                ProgressView("Транскрибируем файл локально на устройстве…")
            } else if voice.isListening {
                HStack(spacing: 8) {
                    Circle()
                        .fill(JusticiaTheme.red)
                        .frame(width: 9, height: 9)
                    Text("Микрофон активен. Текст останется локальным, пока вы сами не выберете дальнейшее действие.")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
            } else {
                Label(
                    "Для аудиофайлов используется только on-device распознавание. Если оно недоступно на этом Mac, «Юстиция» остановится и сообщит об этом.",
                    systemImage: "lock.shield"
                )
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)
            }

            if let error = voice.errorMessage {
                HStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(JusticiaTheme.red)
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.red)
                }
            }
        }
        .justiciaCard()
    }

    private var transcriptCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("Транскрипт")
                    .font(.headline)
                Spacer()
                if !voice.transcript.isEmpty {
                    Button("Очистить") {
                        voice.clearTranscript()
                        importedAudioName = nil
                        savedMessage = nil
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                }
            }

            if voice.transcript.isEmpty {
                VStack(spacing: 10) {
                    JusticiaIconTile(systemName: "text.quote", color: JusticiaTheme.secondaryInk, size: 42)
                    Text("Текст появится после записи или обработки аудиофайла.")
                        .font(.subheadline)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity, minHeight: 320)
            } else {
                ScrollView {
                    Text(voice.transcript)
                        .font(.body)
                        .lineSpacing(5)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .topLeading)
                        .padding(.vertical, 4)
                }
                .frame(minHeight: 320)
            }
        }
        .justiciaCard()
    }

    private var sidePanel: some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 10) {
                Text("Сохранение в дело")
                    .font(.headline)

                if let matter = workspace.selectedMatter {
                    HStack(spacing: 9) {
                        JusticiaIconTile(systemName: "briefcase", color: JusticiaTheme.blue, size: 32)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(matter.displayNumber)
                                .font(.caption.weight(.semibold))
                            Text(matter.title)
                                .font(.caption2)
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                                .lineLimit(2)
                        }
                    }
                } else {
                    Text("Выберите дело в разделе «Дела», чтобы сохранить транскрипт в его локальный корпус.")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }

                Button {
                    Task {
                        let saved = await workspace.saveTranscript(voice.transcript)
                        savedMessage = saved ? "Транскрипт сохранён в выбранное дело." : nil
                    }
                } label: {
                    if workspace.isImporting {
                        ProgressView()
                            .frame(maxWidth: .infinity)
                    } else {
                        Label("Сохранить в дело", systemImage: "square.and.arrow.down")
                            .frame(maxWidth: .infinity)
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(
                    workspace.selectedMatter == nil
                        || voice.transcript.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                        || workspace.isImporting
                )

                if let savedMessage {
                    Label(savedMessage, systemImage: "checkmark.circle.fill")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.green)
                }

                if let error = workspace.errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.red)
                }
            }
            .justiciaCard()

            VStack(alignment: .leading, spacing: 10) {
                Text("Что дальше")
                    .font(.headline)
                instruction("1", "Проверьте текст и исправьте имена, даты и цифры.")
                instruction("2", "Сохраните транскрипт в нужное дело.")
                instruction("3", "После сохранения документ попадает в тот же локальный зашифрованный корпус и может участвовать в поиске по делу.")
            }
            .justiciaCard()

            VStack(alignment: .leading, spacing: 9) {
                Text("Конфиденциальность")
                    .font(.headline)
                Label("Облачная отправка не включается автоматически.", systemImage: "icloud.slash")
                    .font(.caption)
                Label("Файловая транскрибация требует on-device режима.", systemImage: "desktopcomputer.and.arrow.down")
                    .font(.caption)
            }
            .foregroundStyle(JusticiaTheme.secondaryInk)
            .justiciaCard()
        }
    }

    private var statusText: String {
        if voice.isTranscribingFile { return "Идёт локальная обработка выбранного файла" }
        if voice.isListening { return "Говорите — текст будет собран до нажатия «Остановить»" }
        if !voice.transcript.isEmpty { return "Транскрипт готов к проверке и сохранению" }
        return "Загрузите аудиофайл или начните запись"
    }

    private func instruction(_ number: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 9) {
            Text(number)
                .font(.caption.bold())
                .foregroundStyle(JusticiaTheme.blue)
                .frame(width: 24, height: 24)
                .background(JusticiaTheme.blueSoft)
                .clipShape(Circle())
            Text(text)
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)
        }
    }
}
