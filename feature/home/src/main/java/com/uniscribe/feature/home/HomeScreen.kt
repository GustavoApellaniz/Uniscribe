package com.uniscribe.feature.home

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Main Front-End Screen for UniScribe MVP (Android / Jetpack Compose).
 * 
 * Implements the minimal frictionless flow:
 * Start Listening -> Indicador de Gravação -> Stop -> Processing... -> Resumo -> Copy / Export .txt
 */
enum class LectureState {
    IDLE,
    LISTENING,
    PROCESSING,
    READY,
    ERROR
}

data class LectureSummaryUi(
    val title: String = "",
    val course: String = "",
    val duration: String = "",
    val concepts: List<String> = emptyList(),
    val highlights: List<String> = emptyList(),
    val questions: List<String> = emptyList(),
    val executiveSummary: String = "",
    val filteredTranscript: String = "",
    val rawTranscript: String = ""
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    modifier: Modifier = Modifier,
    onStartListening: () -> Unit = {},
    onStopListening: () -> Unit = {},
    onCopySummary: (String) -> Unit = {},
    onExportTxt: (String) -> Unit = {}
) {
    var currentState by remember { mutableStateOf(LectureState.IDLE) }
    var lectureTitle by remember { mutableStateOf("Aula de Redes — Camada de Transporte") }
    var summaryData by remember { mutableStateOf(LectureSummaryUi()) }
    var selectedTab by remember { mutableStateOf(0) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("UniScribe", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text("MVP Acadêmico", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { paddingValues ->
        Box(
            modifier = modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp),
            contentAlignment = Alignment.TopCenter
        ) {
            when (currentState) {
                LectureState.IDLE -> {
                    IdleView(
                        lectureTitle = lectureTitle,
                        onTitleChange = { lectureTitle = it },
                        onStart = {
                            currentState = LectureState.LISTENING
                            onStartListening()
                        }
                    )
                }

                LectureState.LISTENING -> {
                    ListeningView(
                        lectureTitle = lectureTitle,
                        onStop = {
                            currentState = LectureState.PROCESSING
                            onStopListening()
                        }
                    )
                }

                LectureState.PROCESSING -> {
                    ProcessingView(
                        onFinished = {
                            summaryData = LectureSummaryUi(
                                title = lectureTitle,
                                course = "Redes de Computadores",
                                duration = "45 min",
                                concepts = listOf(
                                    "TCP: Protocolo confiável orientado à conexão.",
                                    "Three-Way Handshake: Estabelecimento em 3 vias (SYN, SYN-ACK, ACK).",
                                    "UDP: Datagramas sem confirmação de entrega para baixa latência."
                                ),
                                highlights = listOf(
                                    "Ponto de Prova: TCP realiza retransmissão de pacotes; UDP descarta sem confirmar.",
                                    "Porta 53 do DNS: Utiliza UDP para consultas rápidas e TCP para transferências de zona."
                                ),
                                executiveSummary = "Síntese dos protocolos de transporte TCP e UDP, contrastando garantia de entrega com latência reduzida.",
                                filteredTranscript = "Definição de TCP e UDP na camada de transporte. O TCP é orientado à conexão...",
                                rawTranscript = "Bom dia pessoal... é... vamos começar falando de TCP e UDP..."
                            )
                            currentState = LectureState.READY
                        }
                    )
                }

                LectureState.READY -> {
                    ReadyView(
                        summary = summaryData,
                        selectedTab = selectedTab,
                        onTabChange = { selectedTab = it },
                        onCopy = { onCopySummary(summaryData.executiveSummary) },
                        onExport = { onExportTxt(summaryData.title) },
                        onNewLecture = {
                            currentState = LectureState.IDLE
                        }
                    )
                }

                LectureState.ERROR -> {
                    Text("Ocorreu um erro no processamento. Toque para voltar.")
                }
            }
        }
    }
}

@Composable
fun IdleView(
    lectureTitle: String,
    onTitleChange: (String) -> Unit,
    onStart: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        OutlinedTextField(
            value = lectureTitle,
            onValueChange = onTitleChange,
            label = { Text("Título da Aula") },
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Large Start Listening Action Button
        Box(
            modifier = Modifier
                .size(110.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.primary),
            contentAlignment = Alignment.Center
        ) {
            IconButton(
                onClick = onStart,
                modifier = Modifier.fillMaxSize()
            ) {
                Icon(
                    imageVector = Icons.Default.Mic,
                    contentDescription = "Start Listening",
                    tint = Color.White,
                    modifier = Modifier.size(54.dp)
                )
            }
        }

        Text(
            text = "Start Listening",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )

        Text(
            text = "Toque para gravar. A IA gerará a transcrição e o resumo estruturado ao final.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
fun ListeningView(
    lectureTitle: String,
    onStop: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .clip(CircleShape)
                    .background(Color.Red)
            )
            Text(
                "GRAVANDO AULA",
                color = Color.Red,
                fontWeight = FontWeight.Bold,
                fontSize = 14.sp
            )
        }

        Text(
            lectureTitle,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold
        )

        // Waveform / Audio Level Indicator Placeholder
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(120.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
            contentAlignment = Alignment.Center
        ) {
            Text("Capturando áudio via AudioRecord (16kHz PCM)...")
        }

        Spacer(modifier = Modifier.height(24.dp))

        Button(
            onClick = onStop,
            colors = ButtonDefaults.buttonColors(containerColor = Color.Red),
            modifier = Modifier
                .fillMaxWidth(0.6f)
                .height(52.dp)
        ) {
            Icon(Icons.Default.Stop, contentDescription = null)
            Spacer(modifier = Modifier.width(8.dp))
            Text("Stop", fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
fun ProcessingView(
    onFinished: () -> Unit
) {
    LaunchedEffect(Unit) {
        kotlinx.coroutines.delay(1800)
        onFinished()
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        CircularProgressIndicator(modifier = Modifier.size(64.dp))
        Spacer(modifier = Modifier.height(24.dp))
        Text("Processing...", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Spacer(modifier = Modifier.height(8.dp))
        Text("Transcrevendo com Whisper e gerando resumo com Gemini...", color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun ReadyView(
    summary: LectureSummaryUi,
    selectedTab: Int,
    onTabChange: (Int) -> Unit,
    onCopy: () -> Unit,
    onExport: () -> Unit,
    onNewLecture: () -> Unit
) {
    val scrollState = rememberScrollState()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(summary.title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            OutlinedButton(
                onClick = onCopy,
                modifier = Modifier.weight(1f)
            ) {
                Icon(Icons.Default.ContentCopy, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(6.dp))
                Text("Copy")
            }

            Button(
                onClick = onExport,
                modifier = Modifier.weight(1f)
            ) {
                Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(6.dp))
                Text("Export .txt")
            }
        }

        TabRow(selectedTabIndex = selectedTab) {
            Tab(selected = selectedTab == 0, onClick = { onTabChange(0) }, text = { Text("Resumo") })
            Tab(selected = selectedTab == 1, onClick = { onTabChange(1) }, text = { Text("Filtrada") })
            Tab(selected = selectedTab == 2, onClick = { onTabChange(2) }, text = { Text("Bruta") })
        }

        when (selectedTab) {
            0 -> {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("Conceitos Principais", fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                        summary.concepts.forEach { concept ->
                            Text("• $concept")
                        }

                        Divider()

                        Text("Destaques de Prova", fontWeight = FontWeight.Bold, color = Color.Red)
                        summary.highlights.forEach { highlight ->
                            Text("▶ $highlight")
                        }

                        Divider()

                        Text("Síntese Executiva", fontWeight = FontWeight.Bold)
                        Text(summary.executiveSummary)
                    }
                }
            }
            1 -> {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Text(summary.filteredTranscript, modifier = Modifier.padding(16.dp))
                }
            }
            2 -> {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Text(summary.rawTranscript, modifier = Modifier.padding(16.dp))
                }
            }
        }

        TextButton(
            onClick = onNewLecture,
            modifier = Modifier.align(Alignment.CenterHorizontally)
        ) {
            Text("Gravar Nova Aula")
        }
    }
}
