declare module 'react-native-qrcode-svg' {
    import { Component } from 'react';
    interface QRCodeProps {
        value: string;
        size?: number;
        color?: string;
        backgroundColor?: string;
        logo?: any;
        logoSize?: number;
        logoBackgroundColor?: string;
        logoBorderRadius?: number;
        logoMargin?: number;
        ecl?: 'L' | 'M' | 'Q' | 'H';
        getRef?: (ref: any) => void;
        onError?: (error: any) => void;
        quietZone?: number;
    }
    export default class QRCode extends Component<QRCodeProps> { }
}
