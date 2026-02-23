import { IconSymbol } from '@/components/ui/icon-symbol';
import { useAuth } from '@/services/auth';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { useRouter } from 'expo-router';
import React, { useMemo, useState } from 'react';
import {
    Alert,
    Image,
    ScrollView,
    StyleSheet,
    Text,
    TouchableOpacity,
    View
} from 'react-native';
import QRCode from 'react-native-qrcode-svg';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

// Initial mock data
const INITIAL_TRANSACTIONS = [
    { id: '1', type: 'earned', label: 'Reported Pothole on MG Road', coins: 15, date: '2 hours ago' },
    { id: '2', type: 'earned', label: 'Helped Clear Fallen Tree', coins: 25, date: '5 hours ago' },
    { id: '3', type: 'spent', label: 'Redeemed at QuickMart', coins: 10, date: 'Yesterday' },
];

export default function WalletScreen() {
    const insets = useSafeAreaInsets();
    const { user } = useAuth();
    const router = useRouter();

    const [transactions, setTransactions] = useState(INITIAL_TRANSACTIONS);
    const [isScanning, setIsScanning] = useState(false);
    const [permission, requestPermission] = useCameraPermissions();

    // Generate a mock wallet address from user id
    const walletAddress = useMemo(() => {
        if (!user?.id) return '0x0000...0000';
        const hash = user.id.replace(/-/g, '').substring(0, 20);
        return `0x${hash}`;
    }, [user]);

    // Calculate dynamic mock balance
    const balance = useMemo(() => {
        return transactions.reduce((acc, tx) => {
            return tx.type === 'earned' ? acc + tx.coins : acc - tx.coins;
        }, 120); // base balance
    }, [transactions]);

    const handleScanPress = async () => {
        if (!permission?.granted) {
            const { granted } = await requestPermission();
            if (!granted) {
                Alert.alert("Camera Permission", "Need camera permission to scan QR codes.");
                return;
            }
        }
        setIsScanning(true);
    };

    const handleBarCodeScanned = ({ data }: { data: string }) => {
        setIsScanning(false);

        // Simulate a payment/transfer based on scanned data
        const amount = 15; // fixed mock amount
        if (balance < amount) {
            Alert.alert("Insufficient Balance", "You don't have enough RoadCoins.");
            return;
        }

        Alert.alert(
            "Transfer RoadCoins",
            `Send ${amount} STC to Wallet:\n${data.substring(0, 12)}...?`,
            [
                { text: "Cancel", style: "cancel" },
                {
                    text: "Confirm",
                    onPress: () => {
                        const newTx = {
                            id: Date.now().toString(),
                            type: 'spent',
                            label: `Sent to ${data.substring(0, 8)}...`,
                            coins: amount,
                            date: 'Just now'
                        };
                        setTransactions([newTx, ...transactions]);
                        Alert.alert("Success", `${amount} STC transferred successfully!`);
                    }
                }
            ]
        );
    };

    if (isScanning) {
        return (
            <View style={{ flex: 1, backgroundColor: '#000' }}>
                <CameraView
                    style={StyleSheet.absoluteFillObject}
                    facing="back"
                    onBarcodeScanned={handleBarCodeScanned}
                    barcodeScannerSettings={{
                        barcodeTypes: ["qr"],
                    }}
                />
                <View style={[styles.scannerOverlay, { paddingTop: insets.top + 20 }]}>
                    <TouchableOpacity
                        style={styles.closeScannerBtn}
                        onPress={() => setIsScanning(false)}
                    >
                        <Text style={styles.closeScannerText}>Cancel</Text>
                    </TouchableOpacity>
                    <View style={styles.scannerTarget} />
                    <Text style={styles.scannerPrompt}>Scan Store QR to Pay</Text>
                </View>
            </View>
        );
    }

    return (
        <View style={styles.container}>
            {/* Header */}
            <View style={[styles.header, { paddingTop: insets.top }]}>
                <View style={styles.headerContent}>
                    <Text style={styles.headerTitle}>Wallet</Text>
                    <TouchableOpacity
                        style={styles.closeButton}
                        onPress={() => router.back()}
                    >
                        <Text style={styles.closeButtonText}>Done</Text>
                    </TouchableOpacity>
                </View>
            </View>

            <ScrollView showsVerticalScrollIndicator={false}>
                {/* Balance Card */}
                <View style={styles.balanceCard}>
                    <View style={styles.balanceTop}>
                        <Image
                            source={require('@/assets/images/coin-icon.png')}
                            style={styles.coinImage}
                        />
                        <View style={styles.balanceInfo}>
                            <Text style={styles.balanceLabel}>RoadCoin Balance</Text>
                            <View style={styles.balanceRow}>
                                <Text style={styles.balanceAmount}>{balance}</Text>
                                <Text style={styles.balanceCurrency}> STC</Text>
                            </View>
                        </View>
                    </View>

                    <View style={styles.balanceDivider} />

                    <View style={styles.actionRow}>
                        <View style={styles.balanceStat}>
                            <Text style={styles.balanceStatValue}>
                                {transactions.filter(t => t.type === 'earned').reduce((a, t) => a + t.coins, 0)}
                            </Text>
                            <Text style={styles.balanceStatLabel}>Earned</Text>
                        </View>

                        <TouchableOpacity style={styles.scanButton} onPress={handleScanPress}>
                            <IconSymbol name="camera.viewfinder" size={20} color="#000" />
                            <Text style={styles.scanButtonText}>Scan to Pay</Text>
                        </TouchableOpacity>

                        <View style={styles.balanceStat}>
                            <Text style={[styles.balanceStatValue, { color: '#FF9500' }]}>
                                {transactions.filter(t => t.type === 'spent').reduce((a, t) => a + t.coins, 0)}
                            </Text>
                            <Text style={styles.balanceStatLabel}>Spent</Text>
                        </View>
                    </View>
                </View>

                {/* QR Code Section */}
                <View style={styles.qrSection}>
                    <Text style={styles.sectionTitle}>Receive Coins</Text>
                    <Text style={styles.qrSubtext}>Store owners can scan this to reward you</Text>
                    <View style={styles.qrContainer}>
                        <QRCode
                            value={walletAddress}
                            size={180}
                            backgroundColor="#FFFFFF"
                            color="#000000"
                        />
                    </View>
                    <Text style={styles.walletAddress}>{walletAddress}</Text>
                </View>

                {/* Transaction History */}
                <View style={styles.txSection}>
                    <Text style={styles.sectionTitle}>Recent Activity</Text>
                    {transactions.map((tx) => (
                        <View key={tx.id} style={styles.txRow}>
                            <View style={[
                                styles.txIcon,
                                { backgroundColor: tx.type === 'earned' ? 'rgba(52, 199, 89, 0.12)' : 'rgba(255, 149, 0, 0.12)' }
                            ]}>
                                <Text style={{ fontSize: 16 }}>{tx.type === 'earned' ? '↓' : '↑'}</Text>
                            </View>
                            <View style={styles.txInfo}>
                                <Text style={styles.txLabel} numberOfLines={1}>{tx.label}</Text>
                                <Text style={styles.txDate}>{tx.date}</Text>
                            </View>
                            <Text style={[
                                styles.txAmount,
                                { color: tx.type === 'earned' ? '#34C759' : '#FF9500' }
                            ]}>
                                {tx.type === 'earned' ? '+' : '-'}{tx.coins} STC
                            </Text>
                        </View>
                    ))}
                </View>

                <View style={{ height: 40 }} />
            </ScrollView>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#F5F5F5',
    },
    header: {
        backgroundColor: '#000000',
        paddingBottom: 0,
    },
    headerContent: {
        height: 56,
        flexDirection: 'row',
        justifyContent: 'center',
        alignItems: 'center',
        paddingHorizontal: 16,
    },
    headerTitle: {
        fontSize: 20,
        fontWeight: '700',
        color: '#FFFFFF',
    },
    closeButton: {
        position: 'absolute',
        right: 16,
        padding: 8,
    },
    closeButtonText: {
        color: '#34C759',
        fontSize: 16,
        fontWeight: '600',
    },
    balanceCard: {
        backgroundColor: '#000000',
        paddingHorizontal: 24,
        paddingTop: 8,
        paddingBottom: 24,
        borderBottomLeftRadius: 28,
        borderBottomRightRadius: 28,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.15,
        shadowRadius: 10,
        elevation: 8,
    },
    balanceTop: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    coinImage: {
        width: 64,
        height: 64,
        borderRadius: 32,
        marginRight: 16,
    },
    balanceInfo: {
        flex: 1,
    },
    balanceLabel: {
        fontSize: 13,
        fontWeight: '500',
        color: '#999999',
        marginBottom: 4,
    },
    balanceRow: {
        flexDirection: 'row',
        alignItems: 'baseline',
    },
    balanceAmount: {
        fontSize: 38,
        fontWeight: '800',
        color: '#FFFFFF',
    },
    balanceCurrency: {
        fontSize: 16,
        fontWeight: '600',
        color: '#FFD700',
    },
    balanceDivider: {
        height: 1,
        backgroundColor: '#333333',
        marginVertical: 18,
    },
    actionRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
    },
    balanceStat: {
        alignItems: 'center',
        width: 70,
    },
    balanceStatValue: {
        fontSize: 18,
        fontWeight: '700',
        color: '#34C759',
    },
    balanceStatLabel: {
        fontSize: 12,
        fontWeight: '500',
        color: '#888888',
        marginTop: 4,
    },
    scanButton: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#FFD700',
        paddingHorizontal: 16,
        paddingVertical: 10,
        borderRadius: 20,
    },
    scanButtonText: {
        color: '#000000',
        fontSize: 14,
        fontWeight: '700',
        marginLeft: 6,
    },
    qrSection: {
        backgroundColor: '#FFFFFF',
        marginHorizontal: 16,
        marginTop: 20,
        borderRadius: 16,
        padding: 24,
        alignItems: 'center',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.05,
        shadowRadius: 6,
        elevation: 3,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: '700',
        color: '#000000',
        marginBottom: 4,
        alignSelf: 'flex-start',
    },
    qrSubtext: {
        fontSize: 13,
        color: '#888888',
        marginBottom: 20,
        alignSelf: 'flex-start',
    },
    qrContainer: {
        padding: 16,
        backgroundColor: '#FFFFFF',
        borderRadius: 16,
        borderWidth: 1,
        borderColor: '#E5E5E5',
    },
    walletAddress: {
        fontSize: 12,
        fontWeight: '600',
        color: '#999999',
        marginTop: 12,
        fontFamily: 'monospace',
    },
    txSection: {
        backgroundColor: '#FFFFFF',
        marginHorizontal: 16,
        marginTop: 16,
        borderRadius: 16,
        padding: 20,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.05,
        shadowRadius: 6,
        elevation: 3,
    },
    txRow: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingVertical: 14,
        borderBottomWidth: 1,
        borderBottomColor: '#F3F4F6',
    },
    txIcon: {
        width: 36,
        height: 36,
        borderRadius: 18,
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: 12,
    },
    txInfo: {
        flex: 1,
    },
    txLabel: {
        fontSize: 14,
        fontWeight: '600',
        color: '#000000',
    },
    txDate: {
        fontSize: 12,
        color: '#999999',
        marginTop: 2,
    },
    txAmount: {
        fontSize: 15,
        fontWeight: '700',
        marginLeft: 8,
    },
    scannerOverlay: {
        flex: 1,
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingBottom: 50,
    },
    closeScannerBtn: {
        alignSelf: 'flex-end',
        marginRight: 20,
        padding: 10,
        backgroundColor: 'rgba(0,0,0,0.5)',
        borderRadius: 20,
    },
    closeScannerText: {
        color: '#FFF',
        fontWeight: '600',
        fontSize: 16,
    },
    scannerTarget: {
        width: 250,
        height: 250,
        borderWidth: 3,
        borderColor: '#FFD700',
        borderRadius: 20,
        backgroundColor: 'transparent',
    },
    scannerPrompt: {
        color: '#FFF',
        fontSize: 16,
        fontWeight: '600',
        backgroundColor: 'rgba(0,0,0,0.6)',
        paddingHorizontal: 24,
        paddingVertical: 12,
        borderRadius: 24,
    },
});
